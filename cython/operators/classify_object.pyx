# classify_object.pyx - Main classification operator

from libc.stdint cimport uint32_t
from libc.stddef cimport size_t
from mathutils import Quaternion, Vector

import numpy as np
import time
import bpy

from . import selection_utils, shm_utils, transform_utils

def classify_and_apply_objects(list selected_objects):
    cdef double start_prep = time.perf_counter()

    cdef list all_original_rots = []
    cdef list all_offsets = []

    # Collect selection into groups and individuals and precompute totals
    cdef list mesh_groups
    cdef list parent_groups
    cdef list full_groups
    cdef list group_names
    cdef int total_verts
    cdef int total_edges
    cdef int total_objects
    cdef uint32_t[::1] vert_counts_mv
    cdef uint32_t[::1] edge_counts_mv
    cdef uint32_t[::1] object_counts_mv
    cdef list group
    mesh_groups, parent_groups, full_groups, group_names, total_verts, total_edges, total_objects = selection_utils.aggregate_object_groups(selected_objects)

    # Create shared memory segments and numpy arrays
    shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(total_verts, total_edges, total_objects, mesh_groups)

    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views

    cdef double end_prep = time.perf_counter()
    print(f"Preparation time elapsed: {(end_prep - start_prep) * 1000:.2f}ms")

    cdef double start_processing = time.perf_counter()

    cdef float[::1] parent_offsets_view
    cdef tuple parent_ref_location
    cdef list all_ref_locations = []

    for group in parent_groups:
        parent_offsets_view, parent_ref_location = transform_utils.compute_offset_transforms(group, len(group))

        # Store reference location as a plain tuple for fast numeric ops later
        all_ref_locations.append(parent_ref_location)
        all_offsets.append(parent_offsets_view)

        for obj in group:
            obj.rotation_mode = 'QUATERNION' 
            all_original_rots.append(obj.rotation_quaternion)

    cdef double end_processing = time.perf_counter()
    print(f"Block processing time elapsed: {(end_processing - start_processing) * 1000:.2f}ms")

    cdef double start_alignment = time.perf_counter()

    # Send classify op to engine
    cdef dict command = {
        "id": 1,
        "op": "classify",
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
    
    cdef list rots = [Quaternion(r) for r in final_response["rots"]]
    cdef list surface_type = final_response["surface_type"]
    cdef list origin = [tuple(o) for o in final_response["origin"]]

    # Compute new locations for each object using C++ rotation of offsets, then add ref location
    cdef list locs = []
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

    cdef double end_alignment = time.perf_counter()
    print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")

    # Apply results
    cdef double start_apply = time.perf_counter()
    cdef int obj_idx = 0
    cdef tuple loc
    for i, group in enumerate(parent_groups):
        delta_quat = rots[i]
        first_obj = group[0]
        cursor_loc = Vector(origin[i]) + first_obj.location
        bpy.context.scene.cursor.location = cursor_loc

        for obj in group:
            local_quat = all_original_rots[obj_idx]
            loc = locs[obj_idx]
            
            obj.rotation_quaternion = (delta_quat @ local_quat).normalized()
            obj.location = Vector(loc)
            obj_idx += 1

    for i, group in enumerate(full_groups):
        surface_type_value = surface_type[i]
        group_name = group_names[i]
        
        # Since the engine is the source of truth, update each object without sending commands back to engine
        if group:  # Make sure group is not empty
            from splatter.property_manager import get_property_manager
            prop_manager = get_property_manager()
            
            # Set group names and surface types for all objects in the group
            for obj in group:
                if hasattr(obj, "classification"):
                    prop_manager.set_group_name(obj, group_name)
                    prop_manager.set_attribute(obj, 'surface_type', surface_type_value, update_group=False, update_engine=False)
    
    cdef double end_apply = time.perf_counter()
    print(f"Application time elapsed: {(end_apply - start_apply) * 1000:.2f}ms")