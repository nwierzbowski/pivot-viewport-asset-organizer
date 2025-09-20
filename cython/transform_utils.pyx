import numpy as np
cimport numpy as cnp
from libc.stdint cimport uint32_t


def compute_offset_transforms(list group, uint32_t num_objects):
    """Compute offsets relative to the first object's location.

    Returns (offsets_view, first_location_tuple)
    """
    cdef object first_obj = group[0]
    # Avoid generator expressions to keep Cython from creating closures inside def/cpdef
    cdef list components = []
    cdef object obj
    cdef tuple diff
    for obj in group:
        diff = (obj.matrix_world.translation - first_obj.matrix_world.translation).to_tuple()
        components.extend(diff)
    cdef cnp.ndarray offsets_array = np.array(components, dtype=np.float32)
    cdef float[::1] offsets_view = offsets_array
    return offsets_view, (first_obj.matrix_world.translation.x, first_obj.matrix_world.translation.y, first_obj.matrix_world.translation.z)
