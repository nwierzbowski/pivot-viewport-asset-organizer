from libc.stdint cimport uint32_t

from splatter.cython_api.bounds_api cimport align_min_bounds as align_min_bounds_cpp
from splatter.cython_api.util_api cimport Vec3, uVec2i

def align_min_bounds(float[:, ::1] verts, float[:, ::1] verts_norm, uint32_t[:, ::1] edges):

    if verts.shape[0] == 0:
        return # Or raise an error
    if verts_norm.shape[0] != verts.shape[0]:
        return # Or raise an error
    if edges.shape[0] == 0:
        return # Or raise an error
    if verts.shape[1] != 3:
        raise ValueError(f"Input array must be Nx3, but got Nx{verts.shape[1]}")
    if verts_norm.shape[1] != 3:
        raise ValueError(f"Input array must be Nx3, but got Nx{verts_norm.shape[1]}")
    if edges.shape[1] != 2:
        raise ValueError(f"Input array must be Mx2, but got Mx{edges.shape[1]}")
    
    

    cdef Vec3* verts_ptr = <Vec3*> &verts[0, 0]
    cdef uint32_t vertCount = verts.shape[0]

    cdef Vec3* verts_norm_ptr = <Vec3*> &verts_norm[0, 0]

    cdef uVec2i* edges_ptr = <uVec2i*> &edges[0, 0]
    cdef uint32_t edgeCount = edges.shape[0]

    cdef Vec3 out_rot, out_trans
    with nogil:
        align_min_bounds_cpp(verts_ptr, verts_norm_ptr, vertCount, edges_ptr, edgeCount, &out_rot, &out_trans)

    return (out_rot.x, out_rot.y, out_rot.z), (out_trans.x, out_trans.y, out_trans.z)