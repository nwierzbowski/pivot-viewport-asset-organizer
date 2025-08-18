from libc.stdint cimport uint32_t

from splatter.cython_api.chull_api cimport say_hello_from_cpp, convex_hull_2D as convex_hull_2D_cpp
from splatter.cython_api.util_api cimport Vec3

import numpy as np


def say_hello():
    """Calls the C++ function and prints a message from C++."""
    with nogil:
        say_hello_from_cpp()

def convex_hull_2D(float[:, ::1] verts):
    """Calls the C++ function to compute the convex hull in 2D."""

    if verts.shape[0] == 0:
        return # Or raise an error
    if verts.shape[1] != 3:
        raise ValueError(f"Input array must be Nx3, but got Nx{verts.shape[1]}")

    cdef Vec3* verts_ptr = <Vec3*> &verts[0, 0]
    cdef uint32_t vertCount = verts.shape[0]

    cdef uint32_t[:] out_idx = np.empty(verts.shape[0], dtype=np.uint32)
    cdef uint32_t* out_ptr = &out_idx[0]
    cdef uint32_t out_count = 0

    with nogil:
        convex_hull_2D_cpp(verts_ptr, vertCount, out_ptr, &out_count)

    return out_idx.base[:out_count]