from libc.stdint cimport uint32_t
from libc.stdlib cimport malloc, free
from mathutils import Quaternion as MathutilsQuaternion

cimport numpy as cnp

import bpy
import numpy as np
import time

from splatter.cython_api.engine_api cimport prepare_object_batch as prepare_object_batch_cpp
from splatter.cython_api.engine_api cimport group_objects as group_objects_cpp
from splatter.cython_api.engine_api cimport apply_rotation as apply_rotation_cpp

from splatter.cython_api.vec_api cimport Vec3, uVec2i
from splatter.cython_api.quaternion_api cimport Quaternion

def align_min_bounds(float[::1] verts_flat, uint32_t[::1] edges_flat, list vert_counts, list edge_counts):
    cdef uint32_t num_objects = len(vert_counts)
    if num_objects == 0:
        return [], []
    
    # Pre-copy Python lists to C arrays for nogil access
    cdef uint32_t *vert_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef uint32_t *edge_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    for i in range(num_objects):
        vert_counts_ptr[i] = vert_counts[i]
        edge_counts_ptr[i] = edge_counts[i]

    cdef Vec3 *verts_ptr = <Vec3 *> &verts_flat[0]
    cdef uVec2i *edges_ptr = <uVec2i *> &edges_flat[0]

    cdef Quaternion *out_rots = <Quaternion *> malloc(num_objects * sizeof(Quaternion))
    cdef Vec3 *out_trans = <Vec3 *> malloc(num_objects * sizeof(Vec3))
    
    with nogil:

        prepare_object_batch_cpp(verts_ptr, edges_ptr, vert_counts_ptr, edge_counts_ptr, num_objects, out_rots, out_trans)
    
    # Convert results to Python lists
    rots = [MathutilsQuaternion((out_rots[i].w, out_rots[i].x, out_rots[i].y, out_rots[i].z)) for i in range(num_objects)]
    trans = [(out_trans[i].x, out_trans[i].y, out_trans[i].z) for i in range(num_objects)]
    
    free(vert_counts_ptr)
    free(edge_counts_ptr)
    free(out_rots)
    free(out_trans)
    
    return rots, trans

# -----------------------------
# Helpers for selection grouping
# -----------------------------

cdef list _get_all_mesh_objects(object coll):
    cdef list objects = []
    cdef object obj
    cdef object child
    for obj in coll.objects:
        if obj.type == 'MESH':
            objects.append(obj)
    for child in coll.children:
        objects.extend(_get_all_mesh_objects(child))
    return objects

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

def _collect_groups_and_individuals(list selected_objects):
    """Return (obj_groups, individual_objects, total_verts, total_edges).
    obj_groups maps top collection -> list of all mesh objects in that top collection.
    """
    cdef object scene_coll = bpy.context.scene.collection
    cdef dict coll_to_top = _build_coll_to_top_map(scene_coll)
    cdef dict mesh_cache = {}
    cdef dict obj_groups = {}
    cdef list individual_objects = []
    cdef int total_verts = 0
    cdef int total_edges = 0
    cdef object obj
    cdef object coll
    cdef object top_coll
    cdef object group_coll
    cdef object o

    for obj in selected_objects:
        group_coll = None
        if obj.users_collection:
            coll = obj.users_collection[0]
            if coll != scene_coll:
                top_coll = coll_to_top.get(coll, None)
                if top_coll is not None:
                    if top_coll not in mesh_cache:
                        mesh_cache[top_coll] = _get_all_mesh_objects(top_coll)
                    if len(mesh_cache[top_coll]) > 1:
                        group_coll = top_coll

        if group_coll is None:
            individual_objects.append(obj)
            if obj.type == 'MESH':
                total_verts += len(obj.data.vertices)
                total_edges += len(obj.data.edges)
        else:
            if group_coll not in obj_groups:
                obj_groups[group_coll] = mesh_cache[group_coll]
                for o in obj_groups[group_coll]:
                    total_verts += len(o.data.vertices)
                    total_edges += len(o.data.edges)

    return obj_groups, individual_objects, total_verts, total_edges

def _make_blocks(dict obj_groups, list individual_objects):
    cdef list blocks = []
    cdef list group
    cdef object obj
    for group in obj_groups.values():
        blocks.append(group)
    for obj in individual_objects:
        blocks.append([obj])
    return blocks

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

cdef void _fill_block_geometry(list group, object group_verts_slice, object group_edges_slice):
    cdef uint32_t curr_group_vert_offset = 0
    cdef uint32_t curr_group_edge_offset = 0
    cdef object mesh
    cdef object obj
    cdef int obj_vert_count
    cdef int obj_edge_count
    cdef object verts_slice
    cdef object edges_slice
    for obj in group:
        obj.rotation_mode = 'QUATERNION'
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
        (component for obj in group for component in (obj.rotation_quaternion.w, obj.rotation_quaternion.x, obj.rotation_quaternion.y, obj.rotation_quaternion.z)),
        dtype=np.float32,
        count=num_objects * 4,
    )
    cdef float[::1] rotations_view = rotations_array

    cdef cnp.ndarray offsets_array = np.fromiter(
        (component for obj in group for component in (obj.location - first_obj.location).to_tuple()),
        dtype=np.float32,
        count=num_objects * 3,
    )
    cdef float[::1] offsets_view = offsets_array

    # Return memoryviews to keep arrays alive via references
    return rotations_view, offsets_view

cdef tuple _as_typed_views(object group_verts_slice, object group_edges_slice):
    cdef float[::1] group_verts_view = group_verts_slice
    cdef uint32_t[::1] group_edges_view = group_edges_slice
    return group_verts_view, group_edges_view

def align_to_axes_batch(list selected_objects):
    start_prep = time.perf_counter()
    cdef cnp.ndarray all_verts
    cdef cnp.ndarray all_edges

    cdef list all_vert_counts = []
    cdef list all_edge_counts = []
    cdef list batch_items = []
    cdef list all_original_rots = []  # flat list of tuples
    
    cdef list rots
    cdef list trans

    # Collect selection into groups and individuals and precompute totals
    cdef dict obj_groups
    cdef list individual_objects
    cdef int total_verts
    cdef int total_edges
    obj_groups, individual_objects, total_verts, total_edges = _collect_groups_and_individuals(selected_objects)

    # Allocate flat buffers
    all_verts = np.empty((total_verts * 3), dtype=np.float32)
    all_edges = np.empty((total_edges * 2), dtype=np.uint32)

    cdef uint32_t curr_all_verts_offset = 0
    cdef uint32_t curr_all_edges_offset = 0
    all_vert_counts = []
    all_edge_counts = []

    end_prep = time.perf_counter()
    print(f"Preparation time elapsed: {(end_prep - start_prep) * 1000:.2f}ms")

    start_processing = time.perf_counter()
    # Build blocks: each block is a list of mesh objects (group or individual)
    cdef list blocks = _make_blocks(obj_groups, individual_objects)

    # Process each block
    cdef list group
    cdef cnp.ndarray group_vert_counts
    cdef cnp.ndarray group_edge_counts
    cdef uint32_t group_vert_count
    cdef uint32_t group_edge_count
    cdef uint32_t num_objects
    cdef uint32_t[::1] vert_counts_view
    cdef uint32_t[::1] edge_counts_view
    cdef uint32_t *vert_counts_ptr
    cdef uint32_t *edge_counts_ptr
    cdef object group_verts_slice
    cdef object group_edges_slice
    cdef float[::1] group_verts_view
    cdef uint32_t[::1] group_edges_view
    cdef float[::1] rotations_view
    cdef float[::1] offsets_view
    cdef Vec3* group_verts_slice_ptr
    cdef uVec2i* group_edges_slice_ptr
    cdef Quaternion* rotations_ptr
    cdef Vec3* offsets_ptr
    cdef object obj

    for group in blocks:
        group_vert_counts, group_edge_counts, group_vert_count, group_edge_count, num_objects = _prepare_block_counts(group)

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
        rotations_view, offsets_view = _compute_transforms(group, num_objects)

        # Convert counts to typed pointers
        vert_counts_view = group_vert_counts
        edge_counts_view = group_edge_counts
        vert_counts_ptr = &vert_counts_view[0]
        edge_counts_ptr = &edge_counts_view[0]

        # Convert slices to typed views/pointers for C++ call
        group_verts_view, group_edges_view = _as_typed_views(group_verts_slice, group_edges_slice)
        group_verts_slice_ptr = <Vec3*> &group_verts_view[0]
        group_edges_slice_ptr = <uVec2i*> &group_edges_view[0]

        # Derive transform pointers
        rotations_ptr = <Quaternion*> &rotations_view[0]
        offsets_ptr = <Vec3*> &offsets_view[0]

        # Apply transform/indexing in C++ for both groups and singletons
        group_objects_cpp(group_verts_slice_ptr, group_edges_slice_ptr, vert_counts_ptr, edge_counts_ptr, offsets_ptr, rotations_ptr, num_objects)

        # Record counts and mapping
        all_vert_counts.append(group_vert_count)
        all_edge_counts.append(group_edge_count)
        batch_items.append(group)
        for obj in group:
            all_original_rots.append(obj.rotation_quaternion)

    end_processing = time.perf_counter()
    print(f"Block processing time elapsed: {(end_processing - start_processing) * 1000:.2f}ms")

    start_alignment = time.perf_counter()

    if all_verts.size > 0:
        
        # Call batched C++ function for all
        rots, trans = align_min_bounds(all_verts, all_edges, all_vert_counts, all_edge_counts)

        end_alignment = time.perf_counter()
        print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")
        
        return rots, trans, batch_items, all_original_rots
    else:
        end_alignment = time.perf_counter()
        print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")
        return [], [], [], []