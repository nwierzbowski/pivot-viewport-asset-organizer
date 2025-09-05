from libc.stdint cimport uint32_t
from libc.stdlib cimport malloc, free

from splatter.cython_api.engine_api cimport standardize_object_transform as standardize_object_transform_cpp
from splatter.cython_api.vec_api cimport Vec3, uVec2i

def align_min_bounds(float[:, ::1] verts_flat, uint32_t[:, ::1] edges_flat, list vert_counts, list edge_counts):
    cdef uint32_t num_objects = len(vert_counts)
    if num_objects == 0:
        return [], []
    
    # Declare loop variables at the top
    cdef uint32_t i, v_count, e_count
    
    # Pre-copy Python lists to C arrays for nogil access
    cdef uint32_t *vert_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef uint32_t *edge_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    for i in range(num_objects):
        vert_counts_ptr[i] = vert_counts[i]
        edge_counts_ptr[i] = edge_counts[i]
    
    cdef uint32_t vert_offset = 0
    cdef uint32_t edge_offset = 0
    cdef Vec3 *verts_ptr = <Vec3 *> &verts_flat[0, 0]
    cdef uVec2i *edges_ptr = <uVec2i *> &edges_flat[0, 0]
    
    cdef Vec3 *out_rots = <Vec3 *> malloc(num_objects * sizeof(Vec3))
    cdef Vec3 *out_trans = <Vec3 *> malloc(num_objects * sizeof(Vec3))
    
    with nogil:
        for i in range(num_objects):
            v_count = vert_counts_ptr[i]
            e_count = edge_counts_ptr[i]
            standardize_object_transform_cpp(&verts_ptr[vert_offset], v_count, &edges_ptr[edge_offset], e_count, &out_rots[i], &out_trans[i])
            vert_offset += v_count
            edge_offset += e_count
    
    # Convert results to Python lists
    rots = [(out_rots[i].x, out_rots[i].y, out_rots[i].z) for i in range(num_objects)]
    trans = [(out_trans[i].x, out_trans[i].y, out_trans[i].z) for i in range(num_objects)]
    
    free(vert_counts_ptr)
    free(edge_counts_ptr)
    free(out_rots)
    free(out_trans)
    
    return rots, trans