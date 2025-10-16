# classify_object.pyx - Main classification operator

from libc.stdint cimport uint32_t
from libc.stddef cimport size_t
from mathutils import Quaternion, Vector, Matrix

import numpy as np
import time
import bpy

from . import selection_utils, shm_utils, transform_utils, edition_utils
from splatter import engine_state
from splatter.property_manager import (
    GROUP_COLLECTION_PROP,
    CLASSIFICATION_ROOT_COLLECTION_NAME,
    CLASSIFICATION_COLLECTION_PROP
)



def set_origin_and_preserve_children(obj, new_origin_world):
    """
    Sets the origin of an object to a new world-space location while keeping
    its mesh and all of its children visually stationary.

    """
    old_matrix_world = obj.matrix_world.copy()

    if not hasattr(obj, 'data') or not hasattr(obj.data, 'transform'):
        # For empties (objects without mesh data), move directly to the origin while keeping children stationary
        new_matrix = obj.matrix_world.copy()
        new_matrix.translation = new_origin_world
        obj.matrix_world = new_matrix

        correction_matrix = obj.matrix_world.inverted() @ old_matrix_world

        if obj.children:
            for child in obj.children:
                child.matrix_parent_inverse = correction_matrix @ child.matrix_parent_inverse
        return

    inv_matrix = obj.matrix_world.to_3x3().inverted()
    world_translation_offset = new_origin_world - old_matrix_world.translation
    local_translation_offset = inv_matrix @ world_translation_offset

    obj.data.transform(Matrix.Translation(-local_translation_offset))

    new_matrix = obj.matrix_world.copy()
    new_matrix.translation = new_origin_world
    obj.matrix_world = new_matrix

    correction_matrix = obj.matrix_world.inverted() @ old_matrix_world

    if obj.children:
        for child in obj.children:
            # The new parent_inverse is the correction applied to the old one.
            child.matrix_parent_inverse = correction_matrix @ child.matrix_parent_inverse

def classify_and_apply_objects(list selected_objects, collection):
    cdef double start_prep = time.perf_counter()
    cdef double end_prep, start_processing, end_processing, start_alignment, end_alignment
    cdef double face_prep_start, face_prep_end, classify_wait_start, classify_wait_end
    cdef double faces_send_start, faces_send_end, faces_wait_start, faces_wait_end
    cdef double start_apply, end_apply, total_face_pipeline_start, total_face_pipeline_end

    cdef list all_original_rots = []

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
    mesh_groups, parent_groups, full_groups, group_names, total_verts, total_edges, total_objects = selection_utils.aggregate_object_groups(selected_objects, collection)

    group_membership_snapshot = {}
    for idx in range(len(full_groups)):
        group_name = group_names[idx]
        group = full_groups[idx]
        if group_name is None:
            continue
        group_membership_snapshot[group_name] = [obj.name for obj in group if obj is not None]

    # Create shared memory segments and numpy arrays for verts/edges only
    shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(total_verts, total_edges, total_objects, mesh_groups)

    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv, offsets_mv = count_memory_views

    start_processing = time.perf_counter()

    cdef size_t current_offset_idx = 0
    cdef size_t group_size
    cdef size_t group_offset_size
    cdef float[::1] group_offsets_slice
    cdef object first_obj

    cdef Py_ssize_t group_idx
    cdef list all_parent_offsets = []

    for group_idx in range(len(parent_groups)):
        group = parent_groups[group_idx]
        mesh_group = mesh_groups[group_idx]
        group_size = len(mesh_group)
        group_offset_size = group_size * 3  # 3 floats per object (x,y,z)
        group_offsets_slice = offsets_mv[current_offset_idx:current_offset_idx + group_offset_size]
        
        parent_offsets = transform_utils.compute_offset_transforms(group, mesh_group, group_offsets_slice)
        all_parent_offsets.append(parent_offsets)

        for obj in group:
            obj.rotation_mode = 'QUATERNION' 
            all_original_rots.append(obj.rotation_quaternion)
        
        current_offset_idx += group_offset_size

    

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

    
    
    # Send classify command and wait for response
    engine.send_command_async(command)
    end_processing = time.perf_counter()
    print(f"Preparation time elapsed: {(end_processing - start_prep) * 1000:.2f}ms")

    # start_alignment = time.perf_counter()
    classify_wait_start = time.perf_counter()
    # face_shm_objects, face_shm_names, face_counts_mv, face_sizes_mv, face_vert_counts_mv, total_faces_count, total_faces = shm_utils.prepare_face_data(total_objects, mesh_groups)
    # faces_shm_name, face_sizes_shm_name = face_shm_names

    # print(f"Time to prepare face data for sending to engine: {(time.perf_counter() - classify_wait_start) * 1000:.2f}ms")

    final_response = engine.wait_for_response(1)  # Wait for response with id=1
    classify_wait_end = time.perf_counter()
    print(f"Time for engine to return classify response: {(classify_wait_end - classify_wait_start) * 1000:.2f}ms")
    
    cdef double post_classify_start = time.perf_counter()
    # if total_faces > 0:
    #     faces_send_start = time.perf_counter()
    #     faces_command = {
    #         "id": 2,
    #         "op": "send_faces",
    #         "shm_faces": faces_shm_name,
    #         "shm_face_sizes": face_sizes_shm_name,
    #         "face_counts": list(face_counts_mv),
    #         "vert_counts": list(vert_counts_mv),
    #         "group_names": group_names,
    #         "object_counts": list(object_counts_mv)
    #     }
        
    #     engine.send_command_async(faces_command)
    #     faces_send_end = time.perf_counter()
    #     total_face_pipeline_start = faces_send_start
        
    #     faces_response = engine.wait_for_response(2)
    
    # Now it's safe to close face shared memory handles
    # for shm in face_shm_objects:
    #     shm.close()
    
    cdef dict groups = final_response["groups"]
    cdef list rots = [Quaternion(groups[name]["rot"]) for name in group_names]
    cdef list surface_type = []
    if edition_utils.is_pro_edition():
        surface_type = [groups[name]["surface_type"] for name in group_names]
    cdef list origin = [tuple(groups[name]["origin"]) for name in group_names]

    # Compute new locations for each object using Cython rotation of offsets, then add ref location
    cdef list locs = []
    cdef Py_ssize_t i, j
    cdef float rx, ry, rz
    cdef list parent_offsets_mv
    cdef list all_rotated_offsets = []

    for i in range(len(parent_groups)):
        # Rotate this group's offsets in-place using numpy for speed
        group = parent_groups[i]
        group_size = <uint32_t> len(group)
        parent_offsets_mv = all_parent_offsets[i]
        rot_matrix = np.array(rots[i].to_matrix())
        offsets_array = np.asarray(parent_offsets_mv).reshape(group_size, 3)
        rotated_offsets = offsets_array @ rot_matrix.T
        rotated_flat = rotated_offsets.flatten()

        # Convert to list for storage
        rotated_offsets_list = [(rotated_flat[j * 3], rotated_flat[j * 3 + 1], rotated_flat[j * 3 + 2]) for j in range(group_size)]
        all_rotated_offsets.append(rotated_offsets_list)

        # Add the engine's origin offset to the reference location for each rotated offset and collect as tuples
        ref_vec = parent_groups[i][0].matrix_world.translation
        origin_vec = Vector(origin[i])
        rx = <float> (ref_vec.x + origin_vec.x)
        ry = <float> (ref_vec.y + origin_vec.y)
        rz = <float> (ref_vec.z + origin_vec.z)
        for j in range(len(group)):
            locs.append((rx + rotated_flat[j * 3], ry + rotated_flat[j * 3 + 1], rz + rotated_flat[j * 3 + 2]))

    # Close shared memory handles in parent process; let engine manage unlinking since it may hold longer
    for shm in shm_objects:
        shm.close()

    # Apply results
    cdef int obj_idx = 0
    cdef tuple loc
    for i, group in enumerate(parent_groups):
        delta_quat = rots[i]
        first_obj = group[0]
        first_world_translation = first_obj.matrix_world.translation.copy()
        target_origin = Vector(origin[i]) + first_world_translation            

        for obj in group:
            local_quat = all_original_rots[obj_idx]
            loc = locs[obj_idx]
            
            obj.location = Vector(loc)
            set_origin_and_preserve_children(obj, target_origin)
            obj.rotation_quaternion = (delta_quat @ local_quat).normalized()
            obj_idx += 1

        bpy.context.scene.cursor.location = target_origin

    if edition_utils.is_pro_edition():
        from splatter.property_manager import get_property_manager
        prop_manager = get_property_manager()

        for i, group in enumerate(full_groups):
            if not group:
                continue

            surface_type_value = surface_type[i]
            group_name = group_names[i]

            for obj in group:
                prop_manager.set_group_name(obj, group_name, collection)
                assign_surface_collection(obj, surface_type_value)

            prop_manager.mark_group_synced(group_name)
        engine_state.update_group_membership_snapshot(group_membership_snapshot, replace=True)
    
    


    end_apply = time.perf_counter()
    
    cdef double post_classify_end = end_apply
    print(f"Post-classification processing time: {(post_classify_end - post_classify_start) * 1000:.2f}ms")

def assign_surface_collection(obj, surface_value):
    """Assign an object to a surface classification collection."""
    surface_key = str(surface_value)
    
    # Get or create pivot root collection
    scene = bpy.context.scene
    pivot_root = bpy.data.collections.get(CLASSIFICATION_ROOT_COLLECTION_NAME)
    if not pivot_root:
        pivot_root = bpy.data.collections.new(CLASSIFICATION_ROOT_COLLECTION_NAME)
        if scene.collection.children.find(pivot_root.name) == -1:
            scene.collection.children.link(pivot_root)
    
    # Get group name for object
    group_name = None
    for coll in obj.users_collection:
        if coll.get(GROUP_COLLECTION_PROP):
            group_name = coll.get(GROUP_COLLECTION_PROP)
            break
    
    if not group_name:
        return
    
    # Find or create group collection
    group_collection = None
    for coll in bpy.data.collections:
        if coll.get(GROUP_COLLECTION_PROP) == group_name:
            group_collection = coll
            break
    
    if not group_collection:
        return
    
    # Get or create surface collection
    surface_collection = None
    for coll in pivot_root.children:
        if coll.get(CLASSIFICATION_COLLECTION_PROP) == surface_key:
            surface_collection = coll
            break
    
    if not surface_collection:
        # Try to reuse existing collection
        existing = bpy.data.collections.get(surface_key)
        if existing:
            if pivot_root.children.find(existing.name) == -1:
                pivot_root.children.link(existing)
            existing[CLASSIFICATION_COLLECTION_PROP] = surface_key
            surface_collection = existing
        else:
            surface_collection = bpy.data.collections.new(surface_key)
            surface_collection[CLASSIFICATION_COLLECTION_PROP] = surface_key
            pivot_root.children.link(surface_collection)
    
    # Link group collection to surface collection
    if surface_collection.children.find(group_collection.name) == -1:
        surface_collection.children.link(group_collection)
    
    # Set metadata
    group_collection[CLASSIFICATION_COLLECTION_PROP] = surface_key
    
    # Unlink from other surface containers
    for coll in pivot_root.children:
        if coll is surface_collection:
            continue
        if coll.children.find(group_collection.name) != -1:
            coll.children.unlink(group_collection)