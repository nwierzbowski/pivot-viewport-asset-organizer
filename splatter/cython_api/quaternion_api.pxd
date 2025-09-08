cdef extern from "../engine/share/quaternion.h" nogil:

    ctypedef struct Quaternion:
        float w, x, y, z