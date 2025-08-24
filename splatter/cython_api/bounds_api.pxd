from libc.stdint cimport uint32_t
from splatter.cython_api.util_api cimport Vec3, uVec2i

cdef extern from "../engine/bounds.h" nogil:
    void align_min_bounds(const Vec3* verts, const Vec3* vert_norms, uint32_t vertCount, const uVec2i* edges, uint32_t edgeCount, Vec3* out_rot, Vec3* out_trans)
