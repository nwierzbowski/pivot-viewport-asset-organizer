from libc.stdint cimport uint32_t
from libc.stddef cimport size_t
from mathutils import Quaternion

import numpy as np
import time

# Import helpers from separate Cython modules
from .selection_utils import aggregate_object_groups
from .shm_utils import create_data_arrays
from .transform_utils import compute_offset_transforms

cdef extern from "classification.h":
    cdef enum SurfaceType:
        Ground
        Wall
        Ceiling

# -----------------------------
# Main
# -----------------------------

def align_to_axes_batch(list selected_objects):


    start_prep = time.perf_counter()

    cdef list all_original_rots = []
    cdef list all_offsets = []

    # Collect selection into groups and individuals and precompute totals
    cdef list mesh_groups
    cdef list parent_groups
    cdef list group_names
    cdef int total_verts
    cdef int total_edges
    cdef int total_objects
    cdef uint32_t[::1] vert_counts_mv
    cdef uint32_t[::1] edge_counts_mv
    cdef uint32_t[::1] object_counts_mv
    cdef list group
    mesh_groups, parent_groups, group_names, total_verts, total_edges, total_objects = aggregate_object_groups(selected_objects)

    # Create shared memory segments and numpy arrays
    shm_objects, shm_names, count_memory_views = create_data_arrays(total_verts, total_edges, total_objects, mesh_groups)

    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views



    end_prep = time.perf_counter()
    print(f"Preparation time elapsed: {(end_prep - start_prep) * 1000:.2f}ms")



    start_processing = time.perf_counter()

    cdef float[::1] parent_offsets_view
    cdef tuple parent_ref_location
    cdef list all_ref_locations = []

    for group in parent_groups:
        parent_offsets_view, parent_ref_location = compute_offset_transforms(group, len(group))

        # Store reference location as a plain tuple for fast numeric ops later
        all_ref_locations.append(parent_ref_location)
        all_offsets.append(parent_offsets_view)

        for obj in group:
            obj.rotation_mode = 'QUATERNION' 
            all_original_rots.append(obj.rotation_quaternion)

    end_processing = time.perf_counter()
    print(f"Block processing time elapsed: {(end_processing - start_processing) * 1000:.2f}ms")



    start_alignment = time.perf_counter()

    # Send prepare op to engine
    command = {
        "id": 1,
        "op": "prepare",
        "shm_verts": verts_shm_name,
        "shm_edges": edges_shm_name,
        "shm_rotations": rotations_shm_name,
        "shm_scales": scales_shm_name,
        "shm_offsets": offsets_shm_name,
        "vert_counts": list(vert_counts_mv),
        "edge_counts": list(edge_counts_mv),
        "object_counts": list(object_counts_mv),
        "group_names": group_names
    }

    from splatter.engine import get_engine_communicator
    engine = get_engine_communicator()
    final_response = engine.send_command(command)
    
    if "ok" not in final_response or not final_response["ok"]:
        raise RuntimeError(f"Engine error: {final_response.get('error', 'Unknown error')}")
    
    rots = [Quaternion(r) for r in final_response["rots"]]

    # Compute new locations for each object using C++ rotation of offsets, then add ref location
    locs = []
    cdef Py_ssize_t i, j
    cdef float rx, ry, rz
    cdef tuple ref_loc_tup
    cdef uint32_t group_size
    cdef float[::1] parent_offsets_mv

    for i in range(len(parent_groups)):
        # Rotate this group's offsets in-place using numpy for speed
        group = parent_groups[i]
        group_size = <uint32_t> len(group)
        parent_offsets_mv = all_offsets[i]
        rot_matrix = np.array(rots[i].to_matrix())
        offsets_array = np.asarray(parent_offsets_mv).reshape(group_size, 3)
        rotated_offsets = offsets_array @ rot_matrix.T
        rotated_flat = rotated_offsets.flatten()

        # Add the reference location to each rotated offset and collect as tuples
        ref_loc_tup = all_ref_locations[i]
        rx = <float> ref_loc_tup[0]
        ry = <float> ref_loc_tup[1]
        rz = <float> ref_loc_tup[2]
        for j in range(len(group)):
            locs.append((rx + rotated_flat[j * 3], ry + rotated_flat[j * 3 + 1], rz + rotated_flat[j * 3 + 2]))

    # Close shared memory handles in parent process; let engine manage unlinking since it may hold longer
    for shm in shm_objects:
        shm.close()

    end_alignment = time.perf_counter()
    print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")

    return rots, locs, parent_groups, all_original_rots, all_ref_locations