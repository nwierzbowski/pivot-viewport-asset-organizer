# standardize.pyx - Classifies and applies transformations to Blender objects.
#
# This module handles:
# - Communicating with the C++ engine to compute object classifications
# - Computing and applying new world-space transforms based on engine output
# - Managing collection hierarchy for surface type classification (Pro edition)

from mathutils import Quaternion, Vector, Matrix

import bpy

from . import selection_utils, shm_utils, edition_utils, group_manager
from pivot import engine_state
from pivot.engine import get_engine_communicator

# Collection metadata keys
GROUP_COLLECTION_PROP = "pivot_group_name"
CLASSIFICATION_ROOT_COLLECTION_NAME = "Pivot"
CLASSIFICATION_COLLECTION_PROP = "pivot_surface_type"


def _setup_pivots_for_groups_return_empties(parent_groups, group_names, origins, first_world_locs):
    """Set up one pivot empty per group with smart empty detection/creation."""
    return selection_utils._setup_pivots_for_groups_return_empties(parent_groups, group_names, origins, first_world_locs)


def _get_or_create_pivot_empty(parent_group, group_name, target_origin):
    """
    Get or create a single pivot empty for the group.
    - If group's collection has exactly one empty, reuse it
    - If group's collection has no empties, create one
    - If group's collection has multiple empties, create a new one and parent existing empties to it
    Only parent the parent objects (from parent_group) to the pivot; children inherit automatically.
    Returns: the pivot empty (which is NOT added to parent_group)
    """
    return selection_utils._get_or_create_pivot_empty(parent_group, group_name, target_origin)


def _apply_transforms_to_pivots(pivots, origins, rots, cogs):
    """Apply position and rotation transforms to pivots.
    Updates pivot positions with origins, then applies rotations by modifying children's matrix_local."""

    for i, pivot in enumerate(pivots):
        delta_quat = rots[i]
        rotation_matrix = delta_quat.to_matrix().to_4x4()
        target_origin = pivot.matrix_world.translation + Vector(cogs[i]) - rotation_matrix @ Vector(cogs[i]) + Vector(origins[i])

        for child in pivot.children:
            child.matrix_local = (Matrix.Translation(Vector(origins[i])).inverted() @ Matrix.Translation(rotation_matrix @ Vector(cogs[i]))) @ rotation_matrix @ Matrix.Translation(Vector(cogs[i])).inverted() @ child.matrix_local 

        pivot.matrix_world.translation = target_origin
        


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


def _send_engine_command_and_get_response(engine, command):
    """Send engine command and handle response with error checking."""
    engine.send_command_async(command)
    final_response = engine.wait_for_response(1)
    
    if not bool(final_response.get("ok", True)):
        error_msg = final_response.get("error", "Unknown engine error")
        raise RuntimeError(f"Engine command failed: {error_msg}")
    
    return final_response


def _close_shared_memory_segments(shm_objects):
    """Close shared memory segments with error handling."""
    for shm in shm_objects:
        try:
            shm.close()
        except Exception as e:
            shm_name = getattr(shm, "name", "<unknown>")
            print(f"Warning: Failed to close shared memory segment '{shm_name}': {e}")


def standardize_groups(list selected_objects):
    """
    Pro Edition: Classify selected groups via engine.
    
    This function handles group guessing and collection hierarchy:
    1. Aggregate objects into groups by collection boundaries and root parents
    2. Set up pivot empties and ensure proper collection organization
    3. Marshal mesh data into shared memory
    4. Send classify_groups command to engine (performs group-level operations)
    5. Compute new transforms from engine response
    6. Apply transforms to objects
    7. Organize results into surface type collections
    
    Args:
        selected_objects: List of Blender objects selected by the user
    """
    
    # --- Aggregation phase ---
    mesh_groups, full_groups, group_names, total_verts, total_edges, total_objects, pivots = \
        selection_utils.aggregate_object_groups(selected_objects)
    core_group_mgr = group_manager.get_group_manager()
    
    # Get engine communicator for the entire function
    engine = get_engine_communicator()
    
    if group_names:
        # Pivots are already created in aggregate_object_groups
        # Use the existing pivots for shared memory setup
        
        # --- Shared memory setup ---
        shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(
            total_verts, total_edges, total_objects, mesh_groups, pivots)
        
        verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
        vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views
        
        # --- Engine communication ---
        command = engine.build_standardize_groups_command(
            verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name,
            list(vert_counts_mv), list(edge_counts_mv), list(object_counts_mv), group_names)
        
        final_response = _send_engine_command_and_get_response(engine, command)
        
        # Close shared memory in parent process
        _close_shared_memory_segments(shm_objects)

        groups = final_response["groups"]
        
        # --- Extract and apply transforms ---
        group_names = list(groups.keys())
        rots = [Quaternion(groups[name]["rot"]) for name in group_names]
        origins = [tuple(groups[name]["origin"]) for name in group_names]
        cogs = [tuple(groups[name]["cog"]) for name in group_names]
        
        # --- Apply transforms to PIVOTS (objects follow via parenting) ---
        _apply_transforms_to_pivots(pivots, origins, rots, cogs)
        
        # Build group membership snapshot
        group_membership_snapshot = engine_state.build_group_membership_snapshot(full_groups, group_names)
        engine_state.update_group_membership_snapshot(group_membership_snapshot, replace=False)

    # Always get surface types for ALL stored groups (for organization)
    surface_types_command = engine.build_get_surface_types_command()
    surface_types_response = engine.send_command(surface_types_command)
    
    if not bool(surface_types_response.get("ok", True)):
        error_msg = surface_types_response.get("error", "Unknown engine error during get_surface_types")
        raise RuntimeError(f"get_surface_types failed: {error_msg}")
    
    all_surface_types = surface_types_response.get("groups", {})
    # print(all_surface_types)

    # --- Always organize ALL groups using surface types ---
    if all_surface_types:
        # Use the response order directly instead of converting to list and back
        # This preserves the engine's ordering and prevents group/surface type misalignment
        all_group_names = list(all_surface_types.keys())
        surface_types = [all_surface_types[name]["surface_type"] for name in all_group_names]
        
        # Verify we have matching counts to prevent misalignment
        if len(all_group_names) != len(surface_types):
            raise RuntimeError(f"Mismatch between group names ({len(all_group_names)}) and surface types ({len(surface_types)})")
        
        core_group_mgr.update_managed_group_names(all_group_names)
        core_group_mgr.set_groups_synced(all_group_names)
        
        from pivot.surface_manager import get_surface_manager
        # Pass as parallel lists with verified alignment to avoid swapping
        get_surface_manager().organize_groups_into_surfaces(all_group_names, surface_types)


def standardize_objects(list objects):
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
    
    # Use evaluated depsgraph to account for modifiers that may add verts/edges
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total_verts = 0
    total_edges = 0
    for obj in mesh_objects:
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        total_verts += len(eval_mesh.vertices)
        total_edges += len(eval_mesh.edges)
    
    if total_verts == 0:
        return
    
    # --- Shared memory setup ---
    shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(
        total_verts, total_edges, len(mesh_objects), mesh_groups, [])  # No pivots for objects
    
    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views
    
    # --- Engine communication: unified array format ---
    # Engine will validate that multiple objects are only used in PRO edition
    engine = get_engine_communicator()
    command = engine.build_standardize_objects_command(
        verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name,
        list(vert_counts_mv), list(edge_counts_mv), [obj.name for obj in mesh_objects])
    engine.send_command_async(command)
    
    final_response = engine.wait_for_response(1)
    
    # Close shared memory in parent process
    for shm in shm_objects:
        try:
            shm_name = getattr(shm, "name", "<unknown>")
            shm.close()
        except Exception as e:
            shm_name = getattr(shm, "name", "<unknown>")
            print(f"Warning: Failed to close shared memory segment '{shm_name}': {e}")
            # Continue with other segments even if one fails
    
    if not bool(final_response.get("ok", True)):
        error_msg = final_response.get("error", "Unknown engine error during classify_objects")
        raise RuntimeError(f"classify_objects failed: {error_msg}")

    # --- Extract engine results ---
    # Engine returns results as a dict keyed by object name
    results = final_response.get("results", {})
    rots = [Quaternion(results[obj.name]["rot"]) for obj in mesh_objects if obj.name in results]
    origins = [tuple(results[obj.name]["origin"]) for obj in mesh_objects if obj.name in results]
    cogs = [tuple(results[obj.name]["cog"]) for obj in mesh_objects if obj.name in results]
    
    # --- Apply transforms directly to objects ---
    for i, obj in enumerate(mesh_objects):
        if i < len(rots) and i < len(origins):
            rot = rots[i]
            # Engine returns origin relative to object's old position - convert to world space
            # origin = obj.matrix_world.translation + Vector(origins[i])
            cog = obj.matrix_world.translation + Vector(cogs[i])
            # start_origin = obj.matrix_world.translation
            
            # First move to new origin
            set_origin_and_preserve_children(obj, cog)
            
            # Then apply rotation around the new origin (current position)
            rotation_matrix = rot.to_matrix().to_4x4()
            current_pos = obj.matrix_world.translation
            # Transform to rotate around current position: T(pos) @ R @ T(-pos)
            transform = Matrix.Translation(current_pos) @ rotation_matrix @ Matrix.Translation(-current_pos)


            # Compute the new origin: current_pos + origins[i] - rot @ cogs[i]
            origin_vector = current_pos + Vector(origins[i]) - rot @ Vector(cogs[i])


            obj.matrix_world = transform @ obj.matrix_world

            set_origin_and_preserve_children(obj, origin_vector)
            
            # Set 3D cursor to this object's origin
            bpy.context.scene.cursor.location = obj.matrix_world.translation