# classify_object.pyx - Classifies and applies transformations to Blender objects.
#
# This module handles:
# - Communicating with the C++ engine to compute object classifications
# - Computing and applying new world-space transforms based on engine output
# - Managing collection hierarchy for surface type classification (Pro edition)

from libc.stdint cimport uint32_t
from libc.stddef cimport size_t
from mathutils import Quaternion, Vector, Matrix

import numpy as np
import time
import bpy

from . import selection_utils, shm_utils, transform_utils, edition_utils, group_manager
from pivot import engine_state
from pivot.engine import get_engine_communicator

# Collection metadata keys
GROUP_COLLECTION_PROP = "pivot_group_name"
CLASSIFICATION_ROOT_COLLECTION_NAME = "Pivot"
CLASSIFICATION_COLLECTION_PROP = "pivot_surface_type"



def set_origin_and_preserve_children(obj, new_origin_world):
    """Move object origin to new_origin_world while preserving visual placement of mesh and children."""
    old_matrix = obj.matrix_world.copy()
    inv_matrix = old_matrix.to_3x3().inverted()
    world_offset = new_origin_world - old_matrix.translation
    local_offset = inv_matrix @ world_offset
    correction = Matrix.Translation(-local_offset)

    # Apply correction to mesh if it exists
    if hasattr(obj, 'data') and hasattr(obj.data, 'transform'):
        obj.data.transform(correction)

    # Update world location and fix children parenting
    obj.matrix_world.translation = new_origin_world
    for child in obj.children:
        child.matrix_parent_inverse = correction @ child.matrix_parent_inverse



def _build_classify_groups_command(verts_shm_name, edges_shm_name, rotations_shm_name,
                                   scales_shm_name, offsets_shm_name, vert_counts_mv,
                                   edge_counts_mv, object_counts_mv, group_names):
    """Construct the classify_groups operation command for the engine (Pro edition)."""
    return {
        "id": 1,
        "op": "classify_groups",
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


def _prepare_object_transforms(parent_groups, mesh_groups, offsets_mv):
    """
    Extract offset transforms and rotation modes for all groups.
    Returns: (all_parent_offsets, all_original_rots)
    """
    all_parent_offsets = []
    all_original_rots = []
    
    cdef size_t current_offset_idx = 0
    cdef size_t group_offset_size
    
    for group_idx in range(len(parent_groups)):
        parent_group = parent_groups[group_idx]
        mesh_group = mesh_groups[group_idx]
        group_offset_size = len(mesh_group) * 3  # x, y, z per object
        
        group_offsets_slice = offsets_mv[current_offset_idx:current_offset_idx + group_offset_size]
        parent_offsets = transform_utils.compute_offset_transforms(parent_group, mesh_group, group_offsets_slice)
        all_parent_offsets.append(parent_offsets)
        
        for obj in parent_group:
            obj.rotation_mode = 'QUATERNION'
            # Use world-space rotation to handle objects that may not be root objects
            world_quat = obj.matrix_world.to_quaternion()
            all_original_rots.append(world_quat)
        
        current_offset_idx += group_offset_size
    
    return all_parent_offsets, all_original_rots


def _compute_object_locations(parent_groups, rots, all_parent_offsets):
    """Compute new world locations for all objects after rotation."""
    locations = []
    
    cdef Py_ssize_t i, j
    
    for i in range(len(parent_groups)):
        parent_group = parent_groups[i]
        
        # Rotate offsets by group rotation
        rot_matrix = np.array(rots[i].to_matrix())
        offsets = np.asarray(all_parent_offsets[i])
        rotated_offsets = offsets @ rot_matrix.T
        
        # Compute world-space locations
        ref_location = parent_group[0].matrix_world.translation
        for j in range(len(parent_group)):
            loc = (
                ref_location.x + rotated_offsets[j, 0],
                ref_location.y + rotated_offsets[j, 1],
                ref_location.z + rotated_offsets[j, 2]
            )
            locations.append(loc)
    
    return locations


def _apply_object_transforms(parent_groups, all_original_rots, rots, locations, origins):
    """Apply computed rotations and locations to objects in the scene."""
    cdef int obj_idx = 0
    cdef Py_ssize_t i, j
    
    for i, parent_group in enumerate(parent_groups):
        delta_quat = rots[i]
        first_world_loc = parent_group[0].matrix_world.translation.copy()
        target_origin = Vector(origins[i]) + first_world_loc
        
        for obj in parent_group:
            local_quat = all_original_rots[obj_idx]
            location = locations[obj_idx]
            
            # Compose new rotation and preserve existing scale
            new_rotation = (delta_quat @ local_quat).normalized()
            new_location = Vector(location)
            current_scale = obj.matrix_world.to_scale()
            
            # Build world matrix: Translation * Rotation * Scale
            scale_matrix = Matrix.Diagonal(current_scale).to_4x4()
            rotation_matrix = new_rotation.to_matrix().to_4x4()
            translation_matrix = Matrix.Translation(new_location)
            obj.matrix_world = translation_matrix @ rotation_matrix @ scale_matrix
            
            # Adjust origin to target while preserving visual placement
            set_origin_and_preserve_children(obj, target_origin)
            obj_idx += 1
        
        # Update scene cursor for feedback
        bpy.context.scene.cursor.location = target_origin




def classify_and_apply_groups(list selected_objects):
    """
    Pro Edition: Classify selected groups via engine.
    
    This function handles group guessing and collection hierarchy:
    1. Aggregate objects into groups by collection boundaries and root parents
    2. Marshal mesh data into shared memory
    3. Send classify_groups command to engine (performs group-level operations)
    4. Compute new transforms from engine response
    5. Apply transforms to objects
    6. Organize results into surface type collections
    
    Args:
        selected_objects: List of Blender objects selected by the user
    """
    
    # --- Aggregation phase ---
    mesh_groups, parent_groups, full_groups, group_names, total_verts, total_edges, total_objects = \
        selection_utils.aggregate_object_groups(selected_objects)
    
    if not group_names:
        return
    
    # --- Shared memory setup ---
    shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(
        total_verts, total_edges, total_objects, mesh_groups)
    
    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv, offsets_mv = count_memory_views
    
    # --- Extract transforms and rotation modes ---
    all_parent_offsets, all_original_rots = _prepare_object_transforms(
        parent_groups, mesh_groups, offsets_mv)
    
    # --- Engine communication ---
    command = _build_classify_groups_command(
        verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name,
        vert_counts_mv, edge_counts_mv, object_counts_mv, group_names)
    
    engine = get_engine_communicator()
    engine.send_command_async(command)
    
    final_response = engine.wait_for_response(1)
    
    # Close shared memory in parent process
    for shm in shm_objects:
        try:
            shm_name = getattr(shm, "name", "<unknown>")
        except Exception:
            shm_name = "<unknown>"
        print(f"[Pivot][shm][close] name={shm_name}")
        shm.close()
    
    if not bool(final_response.get("ok", True)):
        error_msg = final_response.get("error", "Unknown engine error during classify_groups")
        raise RuntimeError(f"classify_groups failed: {error_msg}")

    # --- Extract engine results ---
    groups = final_response["groups"]
    rots = [Quaternion(groups[name]["rot"]) for name in group_names]
    origins = [tuple(groups[name]["origin"]) for name in group_names]
    surface_types = [groups[name]["surface_type"] for name in group_names]
    
    # --- Compute and apply transforms ---
    locations = _compute_object_locations(parent_groups, rots, all_parent_offsets)
    _apply_object_transforms(parent_groups, all_original_rots, rots, locations, origins)
    
    # --- Organize into surface collections ---
    # Create group collections and mark as synced
    core_group_mgr = group_manager.get_group_manager()
    core_group_mgr.update_managed_group_names(group_names)
    core_group_mgr.set_groups_synced(group_names)
    # Organize into surface hierarchy
    from pivot.surface_manager import get_surface_manager
    get_surface_manager().organize_groups_into_surfaces(group_names, surface_types)
    
    group_membership_snapshot = engine_state.build_group_membership_snapshot(full_groups, group_names)
    engine_state.update_group_membership_snapshot(group_membership_snapshot, replace=False)


def classify_and_apply_active_objects(list objects):
    """
    Classify and apply standardization to one or more objects.
    
    This unified function handles both single and multiple objects:
    - Single object (both editions): Direct standardization without group guessing
    - Multiple objects (PRO edition only): Batch processing of multiple objects
    
    Args:
        objects: List of Blender objects to classify (one or more)
    
    Raises:
        RuntimeError: If STANDARD edition tries to classify multiple objects
    """
    if not objects:
        return
    
    # Validation: STANDARD edition only supports single object
    if len(objects) > 1 and not edition_utils.is_pro_edition():
        raise RuntimeError(f"STANDARD edition only supports single object classification, got {len(objects)}")
    
    # Filter to mesh objects only
    mesh_objects = [obj for obj in objects if obj.type == 'MESH']
    if not mesh_objects:
        return
    
    # Build mesh data for all objects
    mesh_groups = [[obj] for obj in mesh_objects]
    total_verts = sum(len(obj.data.vertices) for obj in mesh_objects)
    total_edges = sum(len(obj.data.edges) for obj in mesh_objects)
    
    if total_verts == 0:
        return
    
    # --- Shared memory setup ---
    shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(
        total_verts, total_edges, len(mesh_objects), mesh_groups)
    
    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv, offsets_mv = count_memory_views
    
    # --- Extract transforms and rotation modes ---
    parent_groups = [[obj] for obj in mesh_objects]
    all_parent_offsets, all_original_rots = _prepare_object_transforms(
        parent_groups, mesh_groups, offsets_mv)
    
    # --- Engine communication: unified array format ---
    # Engine will validate that multiple objects are only used in PRO edition
    command = {
        "id": 1,
        "op": "classify_objects",
        "shm_verts": verts_shm_name,
        "shm_edges": edges_shm_name,
        "shm_rotations": rotations_shm_name,
        "shm_scales": scales_shm_name,
        "shm_offsets": offsets_shm_name,
        "vert_counts": list(vert_counts_mv),
        "edge_counts": list(edge_counts_mv),
        "object_names": [obj.name for obj in mesh_objects]
    }
    
    engine = get_engine_communicator()
    engine.send_command_async(command)
    
    final_response = engine.wait_for_response(1)
    
    # Close shared memory in parent process
    for shm in shm_objects:
        try:
            shm_name = getattr(shm, "name", "<unknown>")
        except Exception:
            shm_name = "<unknown>"
        print(f"[Pivot][shm][close] name={shm_name}")
        shm.close()
    
    if not bool(final_response.get("ok", True)):
        error_msg = final_response.get("error", "Unknown engine error during classify_objects")
        raise RuntimeError(f"classify_objects failed: {error_msg}")

    # --- Extract engine results ---
    # Engine returns results as a dict keyed by object name
    results = final_response.get("results", {})
    rots = [Quaternion(results[obj.name]["rot"]) for obj in mesh_objects if obj.name in results]
    origins = [tuple(results[obj.name]["origin"]) for obj in mesh_objects if obj.name in results]
    
    # --- Compute and apply transforms ---
    locations = _compute_object_locations(parent_groups, rots, all_parent_offsets)
    _apply_object_transforms(parent_groups, all_original_rots, rots, locations, origins)