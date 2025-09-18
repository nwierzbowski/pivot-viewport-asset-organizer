from libc.stdint cimport uint32_t
from splatter.cython_api.vec_api cimport Vec3
from splatter.cython_api.quaternion_api cimport Quaternion

cdef extern from "../engine/engine.h" nogil:
    void apply_rotation(Vec3* verts, uint32_t vertCount, const Quaternion &rotation);