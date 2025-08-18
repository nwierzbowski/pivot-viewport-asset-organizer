from libc.stdint cimport uint32_t
from splatter.cython_api.util_api cimport Vec3

cdef extern from "../engine/chull.h" nogil:
    void convex_hull_2D(const Vec3* verts, uint32_t vertCount,
                        uint32_t* out_indices, uint32_t* out_count);
