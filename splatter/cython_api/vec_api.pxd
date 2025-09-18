from libc.stdint cimport uint32_t


cdef extern from "../engine/share/vec.h" nogil:
    ctypedef struct Vec3:
        float x, y, z