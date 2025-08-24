from libc.stdint cimport uint32_t


cdef extern from "../engine/util.h" nogil:
    ctypedef struct Vec3:
        float x, y, z

    ctypedef struct uVec2i:
        uint32_t x, y