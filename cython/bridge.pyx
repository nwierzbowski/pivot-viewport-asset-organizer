from libc.stdint cimport uint32_t
from libc.stddef cimport size_t
from mathutils import Quaternion as MathutilsQuaternion, Vector

cimport numpy as cnp

import bpy
import numpy as np
import time
import multiprocessing.shared_memory as shared_memory
import uuid

from splatter.engine import get_engine_communicator

# -----------------------------
# Helpers for selection grouping
# -----------------------------

def _build_coll_to_top_map(object scene_root):
    cdef dict coll_to_top = {}
    cdef object top_coll

    def build_top_map(object current_coll, object current_top):
        for child in current_coll.children:
            coll_to_top[child] = current_top
            build_top_map(child, current_top)

    for top_coll in scene_root.children:
        coll_to_top[top_coll] = top_coll
        build_top_map(top_coll, top_coll)
    return coll_to_top


cdef object get_root_parent(object obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj


cdef list get_all_mesh_descendants(object root):
    cdef list meshes = []
    if root.type == 'MESH' and len(root.data.vertices) != 0:
        meshes.append(root)
    for child in root.children:
        meshes.extend(get_all_mesh_descendants(child))
    return meshes


cdef list get_all_root_objects(object coll):
    cdef list roots = []
    cdef object obj
    for obj in coll.objects:
        if obj.parent is None:
            roots.append(obj)
    for child in coll.children:
        roots.extend(get_all_root_objects(child))
    return roots


def aggregate_object_groups(list selected_objects):
    """Return (mesh_groups, parent_groups, total_verts, total_edges, total_objects).
    mesh_groups is a list of lists, each sublist is a group of mesh objects with verts > 0.
    parent_groups is a list of lists, each sublist contains objects without a parent from the corresponding group.
    Only groups with total_verts > 0 are included.
    """
    cdef object scene_coll = bpy.context.scene.collection
    cdef dict coll_to_top = _build_coll_to_top_map(scene_coll)
    cdef set root_parents = set()
    cdef dict group_map = {}  # top_coll -> list of root_parents
    cdef list scene_roots = []
    cdef list mesh_groups = []
    cdef list parent_groups = []
    cdef int total_verts = 0
    cdef int total_edges = 0
    cdef int total_objects = 0
    cdef object obj
    cdef object root
    cdef object coll
    cdef object top_coll
    cdef list roots
    cdef list all_meshes
    cdef object r
    cdef int group_verts
    cdef int group_edges

    # Collect unique root parents
    for obj in selected_objects:
        root = get_root_parent(obj)
        root_parents.add(root)

    # Group root parents by top-level collection, but treat scene collection roots individually
    for root in root_parents:
        top_coll = scene_coll
        if root.users_collection:
            coll = root.users_collection[0]
            if coll != scene_coll:
                top_coll = coll_to_top.get(coll, scene_coll)
        if top_coll == scene_coll:
            scene_roots.append(root)
        else:
            if top_coll not in group_map:
                group_map[top_coll] = []
            group_map[top_coll].append(root)

    # For each top_coll with selected roots, include all root objects in it
    for top_coll in list(group_map.keys()):
        roots = get_all_root_objects(top_coll)
        group_map[top_coll] = roots

    # Handle scene roots individually
    for root in scene_roots:
        all_meshes = get_all_mesh_descendants(root)
        group_verts = sum(len(m.data.vertices) for m in all_meshes)
        group_edges = sum(len(m.data.edges) for m in all_meshes)
        if group_verts > 0:
            mesh_groups.append(all_meshes)
            parent_groups.append([root])
            total_verts += group_verts
            total_edges += group_edges
            total_objects += len(all_meshes)

    # For each group, collect mesh descendants and build groups
    for roots in group_map.values():
        all_meshes = []
        for r in roots:
            all_meshes.extend(get_all_mesh_descendants(r))
        group_verts = sum(len(m.data.vertices) for m in all_meshes)
        group_edges = sum(len(m.data.edges) for m in all_meshes)
        if group_verts > 0:
            mesh_groups.append(all_meshes)
            parent_groups.append(roots)
            total_verts += group_verts
            total_edges += group_edges
            total_objects += len(all_meshes)

    return mesh_groups, parent_groups, total_verts, total_edges, total_objects

# -----------------------------
# Helpers for shared memory
# -----------------------------

cdef tuple create_data_arrays(uint32_t total_verts, uint32_t total_edges, uint32_t total_objects, list mesh_groups):
    """Create shared memory segments and return shared memory objects, their names, and memory views for count arrays."""
    cdef uint32_t num_groups = len(mesh_groups)
    verts_size = total_verts * 3 * 4  # float32 = 4 bytes
    edges_size = total_edges * 2 * 4  # uint32 = 4 bytes
    vert_counts_size = total_objects * 4  # uint32 = 4 bytes
    edge_counts_size = total_objects * 4  # uint32 = 4 bytes
    num_objects_size = num_groups * 4  # uint32 = 4 bytes
    rotations_size = total_objects * 4 * 4  # float32 = 4 bytes
    scales_size = total_objects * 3 * 4
    offsets_size = total_objects * 3 * 4

    verts_shm_name = f"splatter_verts_{uuid.uuid4().hex}"
    edges_shm_name = f"splatter_edges_{uuid.uuid4().hex}"
    rotations_shm_name = f"splatter_rotations_{uuid.uuid4().hex}"
    scales_shm_name = f"splatter_scales_{uuid.uuid4().hex}"
    offsets_shm_name = f"splatter_offsets_{uuid.uuid4().hex}"

    verts_shm = shared_memory.SharedMemory(create=True, size=verts_size, name=verts_shm_name)
    edges_shm = shared_memory.SharedMemory(create=True, size=edges_size, name=edges_shm_name)
    rotations_shm = shared_memory.SharedMemory(create=True, size=rotations_size, name=rotations_shm_name)
    scales_shm = shared_memory.SharedMemory(create=True, size=scales_size, name=scales_shm_name)
    offsets_shm = shared_memory.SharedMemory(create=True, size=offsets_size, name=offsets_shm_name)

    cdef cnp.ndarray all_verts = np.ndarray((verts_size // 4,), dtype=np.float32, buffer=verts_shm.buf)
    cdef cnp.ndarray all_edges = np.ndarray((edges_size // 4,), dtype=np.uint32, buffer=edges_shm.buf)
    cdef cnp.ndarray rotations = np.ndarray((rotations_size // 4,), dtype=np.float32, buffer=rotations_shm.buf)
    cdef cnp.ndarray scales = np.ndarray((scales_size // 4,), dtype=np.float32, buffer=scales_shm.buf)
    cdef cnp.ndarray offsets = np.ndarray((offsets_size // 4,), dtype=np.float32, buffer=offsets_shm.buf)
    cdef cnp.ndarray vert_counts = np.fromiter((len(obj.data.vertices) for group in mesh_groups for obj in group), dtype=np.uint32, count=total_objects)
    cdef cnp.ndarray edge_counts = np.fromiter((len(obj.data.edges) for group in mesh_groups for obj in group), dtype=np.uint32, count=total_objects)
    cdef cnp.ndarray object_counts = np.fromiter((len(group) for group in mesh_groups), dtype=np.uint32, count=num_groups)

    # Fill transform and geometry arrays in a single pass
    cdef size_t idx_rot = 0
    cdef size_t idx_scale = 0
    cdef size_t idx_offset = 0
    cdef uint32_t curr_verts_offset = 0
    cdef uint32_t curr_edges_offset = 0
    cdef object quat
    cdef object scale_vec
    cdef object trans_vec
    cdef object mesh
    cdef uint32_t obj_vert_count
    cdef uint32_t obj_edge_count
    cdef uint32_t vert_offset
    cdef uint32_t edge_offset

    for group in mesh_groups:
        vert_offset = 0
        edge_offset = 0
        for obj in group:
            # Fill transforms
            quat = obj.matrix_world.to_3x3().to_quaternion()
            rotations[idx_rot] = quat.w
            rotations[idx_rot + 1] = quat.x
            rotations[idx_rot + 2] = quat.y
            rotations[idx_rot + 3] = quat.z
            idx_rot += 4

            scale_vec = obj.matrix_world.to_3x3().to_scale()
            scales[idx_scale] = scale_vec.x
            scales[idx_scale + 1] = scale_vec.y
            scales[idx_scale + 2] = scale_vec.z
            idx_scale += 3

            trans_vec = obj.matrix_world.translation
            offsets[idx_offset] = trans_vec.x
            offsets[idx_offset + 1] = trans_vec.y
            offsets[idx_offset + 2] = trans_vec.z
            idx_offset += 3

            # Fill geometry
            mesh = obj.data
            obj_vert_count = len(mesh.vertices)
            obj_edge_count = len(mesh.edges)

            if obj_vert_count > 0:
                mesh.vertices.foreach_get("co", all_verts[curr_verts_offset + vert_offset:curr_verts_offset + vert_offset + obj_vert_count * 3])
                vert_offset += obj_vert_count * 3

            if obj_edge_count > 0:
                mesh.edges.foreach_get("vertices", all_edges[curr_edges_offset + edge_offset:curr_edges_offset + edge_offset + obj_edge_count * 2])
                edge_offset += obj_edge_count * 2

        curr_verts_offset += vert_offset
        curr_edges_offset += edge_offset

    cdef uint32_t[::1] vert_counts_mv = vert_counts
    cdef uint32_t[::1] edge_counts_mv = edge_counts
    cdef uint32_t[::1] object_counts_mv = object_counts

    shm_objects = (verts_shm, edges_shm, rotations_shm, scales_shm, offsets_shm)
    shm_names = (verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name)
    count_memory_views = (vert_counts_mv, edge_counts_mv, object_counts_mv)

    return shm_objects, shm_names, count_memory_views


cdef tuple _compute_offset_transforms(list group, uint32_t num_objects):
    cdef object first_obj = group[0]
    cdef cnp.ndarray offsets_array = np.fromiter(
        (component for obj in group for component in (obj.matrix_world.translation - first_obj.matrix_world.translation).to_tuple()),
        dtype=np.float32,
        count=num_objects * 3,
    )
    cdef float[::1] offsets_view = offsets_array

    return offsets_view, (first_obj.matrix_world.translation.x, first_obj.matrix_world.translation.y, first_obj.matrix_world.translation.z)


# -----------------------------
# Main
# -----------------------------

def align_to_axes_batch(list selected_objects):


    start_prep = time.perf_counter()

    cdef list all_original_rots = []
    cdef list all_offsets = []

    # Collect selection into groups and individuals and precompute totals
    cdef list mesh_groups
    cdef list parent_groups
    cdef int total_verts
    cdef int total_edges
    cdef int total_objects
    cdef uint32_t[::1] vert_counts_mv
    cdef uint32_t[::1] edge_counts_mv
    cdef uint32_t[::1] object_counts_mv
    cdef list group
    mesh_groups, parent_groups, total_verts, total_edges, total_objects = aggregate_object_groups(selected_objects)

    # Create shared memory segments and numpy arrays
    shm_objects, shm_names, count_memory_views = create_data_arrays(total_verts, total_edges, total_objects, mesh_groups)

    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views



    end_prep = time.perf_counter()
    print(f"Preparation time elapsed: {(end_prep - start_prep) * 1000:.2f}ms")



    start_processing = time.perf_counter()

    cdef float[::1] parent_offsets_view
    cdef tuple parent_ref_location
    cdef list all_ref_locations = []

    for group in parent_groups:
        parent_offsets_view, parent_ref_location = _compute_offset_transforms(group, len(group))

        # Store reference location as a plain tuple for fast numeric ops later
        all_ref_locations.append(parent_ref_location)
        all_offsets.append(parent_offsets_view)

        for obj in group:
            obj.rotation_mode = 'QUATERNION' 
            all_original_rots.append(obj.rotation_quaternion)

    end_processing = time.perf_counter()
    print(f"Block processing time elapsed: {(end_processing - start_processing) * 1000:.2f}ms")



    start_alignment = time.perf_counter()

    # Send prepare op to engine
    command = {
        "id": 1,
        "op": "prepare",
        "shm_verts": verts_shm_name,
        "shm_edges": edges_shm_name,
        "shm_rotations": rotations_shm_name,
        "shm_scales": scales_shm_name,
        "shm_offsets": offsets_shm_name,
        "vert_counts": list(vert_counts_mv),
        "edge_counts": list(edge_counts_mv),
        "object_counts": list(object_counts_mv)
    }

    engine = get_engine_communicator()
    final_response = engine.send_command(command)
    
    if "ok" not in final_response or not final_response["ok"]:
        raise RuntimeError(f"Engine error: {final_response.get('error', 'Unknown error')}")
    
    rots = [MathutilsQuaternion(r) for r in final_response["rots"]]

    # Compute new locations for each object using C++ rotation of offsets, then add ref location
    locs = []
    cdef Py_ssize_t i, j
    cdef float rx, ry, rz
    cdef tuple ref_loc_tup
    cdef uint32_t group_size
    cdef float[::1] parent_offsets_mv

    for i in range(len(parent_groups)):
        # Rotate this group's offsets in-place using numpy for speed
        group = parent_groups[i]
        group_size = <uint32_t> len(group)
        parent_offsets_mv = all_offsets[i]
        rot_matrix = np.array(rots[i].to_matrix())
        offsets_array = np.asarray(parent_offsets_mv).reshape(group_size, 3)
        rotated_offsets = offsets_array @ rot_matrix.T
        rotated_flat = rotated_offsets.flatten()

        # Add the reference location to each rotated offset and collect as tuples
        ref_loc_tup = all_ref_locations[i]
        rx = <float> ref_loc_tup[0]
        ry = <float> ref_loc_tup[1]
        rz = <float> ref_loc_tup[2]
        for j in range(len(group)):
            locs.append((rx + rotated_flat[j * 3], ry + rotated_flat[j * 3 + 1], rz + rotated_flat[j * 3 + 2]))

    # Unlink shared memory after processing
    for shm in shm_objects:
        shm.unlink()

    end_alignment = time.perf_counter()
    print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")

    return rots, locs, parent_groups, all_original_rots, all_ref_locations