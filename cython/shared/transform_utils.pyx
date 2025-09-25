import numpy as np
cimport numpy as cnp


def compute_offset_transforms(list parent_group, list mesh_group, float[::1] group_offsets_mv):
    """Compute offsets relative to the first object's location by modifying group_offsets_mv in-place.
    
    Returns a list of parent object offsets relative to the first parent object.
    """
    cdef size_t group_size = len(mesh_group)
    cdef object first_obj = parent_group[0]
    
    # Get first object's world location
    cdef float first_x = first_obj.matrix_world.translation.x
    cdef float first_y = first_obj.matrix_world.translation.y
    cdef float first_z = first_obj.matrix_world.translation.z
    
    # Make mesh offsets relative to first parent object by subtracting first position
    cdef size_t i
    for i in range(group_size):
        group_offsets_mv[i*3] -= first_x      # x
        group_offsets_mv[i*3 + 1] -= first_y  # y  
        group_offsets_mv[i*3 + 2] -= first_z  # z
    
    # Calculate parent object offsets relative to first parent object
    cdef list parent_offsets = []
    cdef object parent_obj
    cdef float px, py, pz
    for parent_obj in parent_group:
        px = parent_obj.matrix_world.translation.x - first_x
        py = parent_obj.matrix_world.translation.y - first_y
        pz = parent_obj.matrix_world.translation.z - first_z
        parent_offsets.append((px, py, pz))
    
    return parent_offsets
