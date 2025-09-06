from libc.stdint cimport uint32_t
from libc.stdlib cimport malloc, free
from libc.string cimport memcpy

from splatter.cython_api.engine_api cimport prepare_object_batch as prepare_object_batch_cpp
from splatter.cython_api.engine_api cimport group_objects as group_objects_cpp
from splatter.cython_api.vec_api cimport Vec3, uVec2i

def align_min_bounds(float[:, ::1] verts_flat, uint32_t[:, ::1] edges_flat, list vert_counts, list edge_counts):
    cdef uint32_t num_objects = len(vert_counts)
    if num_objects == 0:
        return [], []
    
    # Pre-copy Python lists to C arrays for nogil access
    cdef uint32_t *vert_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef uint32_t *edge_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    for i in range(num_objects):
        vert_counts_ptr[i] = vert_counts[i]
        edge_counts_ptr[i] = edge_counts[i]
    
    cdef Vec3 *verts_ptr = <Vec3 *> &verts_flat[0, 0]
    cdef uVec2i *edges_ptr = <uVec2i *> &edges_flat[0, 0]
    
    cdef Vec3 *out_rots = <Vec3 *> malloc(num_objects * sizeof(Vec3))
    cdef Vec3 *out_trans = <Vec3 *> malloc(num_objects * sizeof(Vec3))
    
    with nogil:
        prepare_object_batch_cpp(verts_ptr, edges_ptr, vert_counts_ptr, edge_counts_ptr, num_objects, out_rots, out_trans)
    
    # Convert results to Python lists
    rots = [(out_rots[i].x, out_rots[i].y, out_rots[i].z) for i in range(num_objects)]
    trans = [(out_trans[i].x, out_trans[i].y, out_trans[i].z) for i in range(num_objects)]
    
    free(vert_counts_ptr)
    free(edge_counts_ptr)
    free(out_rots)
    free(out_trans)
    
    return rots, trans

def align_grouped_min_bounds(float[:, ::1] verts_flat, uint32_t[:, ::1] edges_flat, list vert_counts, list edge_counts, list offsets, list rotations):
    cdef uint32_t num_objects = len(vert_counts)
    if num_objects == 0:
        return verts_flat, edges_flat, [0], [0]
    
    # Calculate total sizes
    cdef uint32_t total_verts = 0
    cdef uint32_t total_edges = 0
    for i in range(num_objects):
        total_verts += vert_counts[i]
        total_edges += edge_counts[i]
    
    # Copy verts_flat and edges_flat to avoid modifying originals
    cdef Vec3 *verts_copy = <Vec3 *>malloc(total_verts * sizeof(Vec3))
    cdef uVec2i *edges_copy = <uVec2i *>malloc(total_edges * sizeof(uVec2i))
    memcpy(verts_copy, &verts_flat[0, 0], total_verts * sizeof(Vec3))
    memcpy(edges_copy, &edges_flat[0, 0], total_edges * sizeof(uVec2i))
    
    # Pre-copy Python lists to C arrays
    cdef uint32_t *vert_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef uint32_t *edge_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef Vec3 *offsets_ptr = <Vec3 *>malloc(num_objects * sizeof(Vec3))
    cdef Vec3 *rotations_ptr = <Vec3 *>malloc(num_objects * sizeof(Vec3))
    for i in range(num_objects):
        vert_counts_ptr[i] = vert_counts[i]
        edge_counts_ptr[i] = edge_counts[i]
        offsets_ptr[i] = Vec3(offsets[i][0], offsets[i][1], offsets[i][2])
        rotations_ptr[i] = Vec3(rotations[i][0], rotations[i][1], rotations[i][2])
    
    with nogil:
        group_objects_cpp(verts_copy, edges_copy, vert_counts_ptr, edge_counts_ptr, offsets_ptr, rotations_ptr, num_objects)
    
    # Copy back to the input arrays (modify in place for the caller)
    memcpy(&verts_flat[0, 0], verts_copy, total_verts * sizeof(Vec3))
    memcpy(&edges_flat[0, 0], edges_copy, total_edges * sizeof(uVec2i))
    
    free(verts_copy)
    free(edges_copy)
    free(vert_counts_ptr)
    free(edge_counts_ptr)
    free(offsets_ptr)
    free(rotations_ptr)
    
    # Return modified arrays and counts for the combined object
    return verts_flat, edges_flat, [total_verts], [total_edges]