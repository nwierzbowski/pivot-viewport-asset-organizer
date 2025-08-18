cdef extern from "../engine/util.h" nogil:
    ctypedef struct Vec3:
        float x, y, z