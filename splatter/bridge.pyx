from libc.stdint cimport uint32_t
from libc.stdlib cimport malloc, free
from mathutils import Quaternion as MathutilsQuaternion, Vector

cimport numpy as cnp

import bpy
import numpy as np
import time

from splatter.cython_api.engine_api cimport prepare_object_batch as prepare_object_batch_cpp
from splatter.cython_api.engine_api cimport group_objects as group_objects_cpp
from splatter.cython_api.engine_api cimport apply_rotation as apply_rotation_cpp

from splatter.cython_api.vec_api cimport Vec3, uVec2i
from splatter.cython_api.quaternion_api cimport Quaternion


def align_min_bounds(float[::1] verts_flat, uint32_t[::1] edges_flat, uint32_t[::1] vert_counts, uint32_t[::1] edge_counts):
    cdef uint32_t num_objects = vert_counts.shape[0]
    if num_objects == 0 or verts_flat.shape[0] == 0:
        return [], []

    # Get direct pointers from memoryviews (no copy)
    cdef uint32_t *vert_counts_ptr = &vert_counts[0]
    cdef uint32_t *edge_counts_ptr = &edge_counts[0]

    cdef Vec3 *verts_ptr = <Vec3 *> &verts_flat[0]
    cdef uVec2i *edges_ptr = <uVec2i *> &edges_flat[0]

    cdef Quaternion *out_rots = <Quaternion *> malloc(num_objects * sizeof(Quaternion))
    cdef Vec3 *out_trans = <Vec3 *> malloc(num_objects * sizeof(Vec3))

    with nogil:
        prepare_object_batch_cpp(verts_ptr, edges_ptr, vert_counts_ptr, edge_counts_ptr, num_objects, out_rots, out_trans)

    # Convert results to Python lists
    rots = [MathutilsQuaternion((out_rots[i].w, out_rots[i].x, out_rots[i].y, out_rots[i].z)) for i in range(num_objects)]
    trans = [(out_trans[i].x, out_trans[i].y, out_trans[i].z) for i in range(num_objects)]

    free(out_rots)
    free(out_trans)

    return rots, trans


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
    """Return (mesh_groups, parent_groups, total_verts, total_edges).
    mesh_groups is a list of lists, each sublist is a group of mesh objects.
    parent_groups is a list of lists, each sublist contains objects without a parent from the corresponding group.
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
    cdef object obj
    cdef object root
    cdef object coll
    cdef object top_coll
    cdef list roots
    cdef list all_meshes
    cdef object r

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
        mesh_groups.append(all_meshes)
        parent_groups.append([root])
        for m in all_meshes:
            total_verts += len(m.data.vertices)
            total_edges += len(m.data.edges)

    # For each group, collect mesh descendants and build groups
    for roots in group_map.values():
        all_meshes = []
        for r in roots:
            all_meshes.extend(get_all_mesh_descendants(r))
        mesh_groups.append(all_meshes)
        parent_groups.append(roots)
        for m in all_meshes:
            total_verts += len(m.data.vertices)
            total_edges += len(m.data.edges)

    return mesh_groups, parent_groups, total_verts, total_edges

# -----------------------------
# Helpers for block processing
# -----------------------------

cdef tuple _prepare_block_counts(list group):
    cdef uint32_t num_objects = len(group)
    cdef cnp.ndarray group_vert_counts = np.fromiter(
        (len(obj.data.vertices) for obj in group), dtype=np.uint32, count=num_objects
    )
    cdef cnp.ndarray group_edge_counts = np.fromiter(
        (len(obj.data.edges) for obj in group), dtype=np.uint32, count=num_objects
    )
    cdef uint32_t group_vert_count = int(group_vert_counts.sum())
    cdef uint32_t group_edge_count = int(group_edge_counts.sum())
    return group_vert_counts, group_edge_counts, group_vert_count, group_edge_count, num_objects


cdef void _fill_block_geometry(list group, float[::1] group_verts_slice, uint32_t[::1] group_edges_slice):
    cdef uint32_t curr_group_vert_offset = 0
    cdef uint32_t curr_group_edge_offset = 0
    cdef object mesh
    cdef object obj
    cdef int obj_vert_count
    cdef int obj_edge_count
    cdef object verts_slice
    cdef object edges_slice
    for obj in group:
        # obj.rotation_mode = 'QUATERNION'
        mesh = obj.data
        obj_vert_count = len(mesh.vertices)
        if obj_vert_count:
            verts_slice = group_verts_slice[curr_group_vert_offset:curr_group_vert_offset + obj_vert_count * 3]
            mesh.vertices.foreach_get("co", verts_slice)
            curr_group_vert_offset += obj_vert_count * 3
        obj_edge_count = len(mesh.edges)
        if obj_edge_count:
            edges_slice = group_edges_slice[curr_group_edge_offset:curr_group_edge_offset + obj_edge_count * 2]
            mesh.edges.foreach_get("vertices", edges_slice)
            curr_group_edge_offset += obj_edge_count * 2


cdef tuple _compute_transforms(list group, uint32_t num_objects):
    cdef object first_obj = group[0]
    cdef cnp.ndarray rotations_array = np.fromiter(
        (component for obj in group for component in obj.matrix_world.to_3x3().to_quaternion()),
        dtype=np.float32,
        count=num_objects * 4,
    )
    cdef float[::1] rotations_view = rotations_array

    cdef cnp.ndarray scales_array = np.fromiter(
        (component for obj in group for component in obj.matrix_world.to_3x3().to_scale()),
        dtype=np.float32,
        count=num_objects * 3,
    )
    cdef float[::1] scales_view = scales_array

    cdef cnp.ndarray offsets_array = np.fromiter(
        (component for obj in group for component in (obj.matrix_world.translation - first_obj.matrix_world.translation).to_tuple()),
        dtype=np.float32,
        count=num_objects * 3,
    )
    cdef float[::1] offsets_view = offsets_array

    # Return memoryviews to keep arrays alive via references
    return rotations_view, scales_view, offsets_view, Vec3(first_obj.matrix_world.translation.x, first_obj.matrix_world.translation.y, first_obj.matrix_world.translation.z)


# -----------------------------
# Main
# -----------------------------

def align_to_axes_batch(list selected_objects):
    start_prep = time.perf_counter()
    cdef cnp.ndarray all_verts
    cdef cnp.ndarray all_edges

    cdef list batch_items = []
    cdef list all_original_rots = []
    
    cdef list all_offsets = []

    cdef list all_scales = []

    cdef cnp.ndarray vert_counts_arr
    cdef cnp.ndarray edge_counts_arr
    cdef Py_ssize_t blocks_len
    cdef Py_ssize_t out_len
    cdef list valid_parent_groups = []

    # Collect selection into groups and individuals and precompute totals
    cdef list mesh_groups
    cdef list parent_groups
    cdef int total_verts
    cdef int total_edges
    mesh_groups, parent_groups, total_verts, total_edges = aggregate_object_groups(selected_objects)

    # Allocate flat buffers
    all_verts = np.empty((total_verts * 3), dtype=np.float32)
    all_edges = np.empty((total_edges * 2), dtype=np.uint32)

    cdef uint32_t curr_all_verts_offset = 0
    cdef uint32_t curr_all_edges_offset = 0

    end_prep = time.perf_counter()
    print(f"Preparation time elapsed: {(end_prep - start_prep) * 1000:.2f}ms")

    start_processing = time.perf_counter()
    # Build blocks: each block is a list of mesh objects (group or individual)
    blocks_len = len(mesh_groups)
    # Preallocate per-block counts (uint32)
    vert_counts_arr = np.empty(blocks_len, dtype=np.uint32)
    edge_counts_arr = np.empty(blocks_len, dtype=np.uint32)
    out_len = 0

    # Process each block
    cdef list group
    cdef cnp.ndarray obj_vert_counts
    cdef cnp.ndarray obj_edge_counts
    cdef uint32_t group_vert_count
    cdef uint32_t group_edge_count
    cdef uint32_t num_objects
    cdef uint32_t[::1] obj_vert_counts_view
    cdef uint32_t[::1] obj_edge_counts_view
    cdef uint32_t *obj_vert_counts_ptr
    cdef uint32_t *obj_edge_counts_ptr
    cdef float[::1] group_verts_slice
    cdef uint32_t[::1] group_edges_slice
    cdef float[::1] rotations_view
    cdef float[::1] scales_view
    cdef float[::1] offsets_view
    cdef Vec3* group_verts_slice_ptr
    cdef uVec2i* group_edges_slice_ptr
    cdef Quaternion* rotations_ptr
    cdef Vec3* offsets_ptr
    cdef Vec3* scales_ptr
    cdef Vec3* offsets_group_ptr
    cdef Quaternion rot_cpp
    cdef uint32_t group_size
    cdef object obj
    cdef float[::1] offsets_mv

    for idx, group in enumerate(mesh_groups):
        obj_vert_counts, obj_edge_counts, group_vert_count, group_edge_count, num_objects = _prepare_block_counts(group)

        # Skip empty blocks (e.g., single object with 0 verts)
        if group_vert_count == 0:
            continue

        # Slices into the big buffers for this block
        group_verts_slice = all_verts[curr_all_verts_offset:curr_all_verts_offset + group_vert_count * 3]
        group_edges_slice = all_edges[curr_all_edges_offset:curr_all_edges_offset + group_edge_count * 2]
        curr_all_verts_offset += group_vert_count * 3
        curr_all_edges_offset += group_edge_count * 2

        # Fill geometry for the block
        _fill_block_geometry(group, group_verts_slice, group_edges_slice)

        # Compute per-object transforms
        rotations_view, scales_view, offsets_view, ref_location = _compute_transforms(group, num_objects)

        # Convert counts to typed pointers
        obj_vert_counts_view = obj_vert_counts
        obj_edge_counts_view = obj_edge_counts
        obj_vert_counts_ptr = &obj_vert_counts_view[0]
        obj_edge_counts_ptr = &obj_edge_counts_view[0]

        # Convert slices to C pointers for C++ call
        group_verts_slice_ptr = <Vec3*> &group_verts_slice[0]
        group_edges_slice_ptr = <uVec2i*> &group_edges_slice[0]

        # Derive transform pointers
        rotations_ptr = <Quaternion*> &rotations_view[0]
        offsets_ptr = <Vec3*> &offsets_view[0]
        scales_ptr = <Vec3*> &scales_view[0]

        # Apply transform/indexing in C++ for both groups and singletons
        group_objects_cpp(group_verts_slice_ptr, group_edges_slice_ptr, obj_vert_counts_ptr, obj_edge_counts_ptr, offsets_ptr, rotations_ptr, scales_ptr, num_objects)

        # Record counts and mapping
        vert_counts_arr[out_len] = group_vert_count
        edge_counts_arr[out_len] = group_edge_count
        
        valid_parent_groups.append(parent_groups[idx])
        
        out_len += 1

    # Resize arrays to actual number of non-empty blocks
    vert_counts_arr = vert_counts_arr[:out_len]
    edge_counts_arr = edge_counts_arr[:out_len]

    cdef float[::1] parent_rotations_view
    cdef float[::1] parent_scales_view
    cdef float[::1] parent_offsets_view
    cdef Vec3 parent_ref_location
    cdef list all_ref_locations = []

    for group in valid_parent_groups:
        parent_rotations_view, parent_scales_view, parent_offsets_view, parent_ref_location = _compute_transforms(group, len(group))

        # Store reference location as a plain tuple for fast numeric ops later
        all_ref_locations.append((parent_ref_location.x, parent_ref_location.y, parent_ref_location.z))
        all_offsets.append(parent_offsets_view)
        all_scales.append(parent_scales_view)

        batch_items.append(group)
        for obj in group:
            obj.rotation_mode = 'QUATERNION'
            all_original_rots.append(obj.rotation_quaternion)

    end_processing = time.perf_counter()
    print(f"Block processing time elapsed: {(end_processing - start_processing) * 1000:.2f}ms")

    start_alignment = time.perf_counter()

    # Call batched C++ function to compute group rotations
    rots, _ = align_min_bounds(all_verts, all_edges, vert_counts_arr, edge_counts_arr)

    # Compute new locations for each object using C++ rotation of offsets, then add ref location
    locs = []
    cdef Py_ssize_t i, j
    cdef float rx, ry, rz
    cdef tuple ref_loc_tup
    for i in range(len(batch_items)):
        # Rotate this group's offsets in-place using C++ for speed
        group = batch_items[i]
        group_size = <uint32_t> len(group)
        offsets_mv = all_offsets[i]
        offsets_group_ptr = <Vec3*> &offsets_mv[0]
        rot_cpp.w = rots[i].w; rot_cpp.x = rots[i].x; rot_cpp.y = rots[i].y; rot_cpp.z = rots[i].z
        apply_rotation_cpp(offsets_group_ptr, group_size, rot_cpp)

        # Add the reference location to each rotated offset and collect as tuples
        ref_loc_tup = all_ref_locations[i]
        rx = <float> ref_loc_tup[0]
        ry = <float> ref_loc_tup[1]
        rz = <float> ref_loc_tup[2]
        for j in range(len(group)):
            locs.append((rx + offsets_mv[j * 3], ry + offsets_mv[j * 3 + 1], rz + offsets_mv[j * 3 + 2]))

    end_alignment = time.perf_counter()
    print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")
    
    return rots, locs, batch_items, all_original_rots, all_ref_locations