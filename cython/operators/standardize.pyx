# classify_object.pyx - Classifies and applies transformations to Blender objects.
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


def _apply_transforms_to_pivots(pivots, rots):
    """Apply group rotations by modifying children's matrix_parent_inverse.
    Pivot empty stays unrotated, but children appear rotated relative to it."""

    for i, pivot in enumerate(pivots):
        delta_quat = rots[i]
        # Apply rotation to each child's matrix_parent_inverse
        # This rotates the children relative to the pivot without rotating the pivot itself
        for child in pivot.children:
            rotation_matrix = delta_quat.to_matrix().to_4x4()
            child.matrix_local = rotation_matrix @ child.matrix_local


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
        vert_counts_mv, edge_counts_mv, object_counts_mv, offsets_mv = count_memory_views
        
        # --- Extract transforms and rotation modes ---
        # all_parent_offsets, all_original_rots = _prepare_object_transforms(
        #     parent_groups, mesh_groups, offsets_mv)
        
        # --- Engine communication ---
        command = engine.build_standardize_groups_command(
            verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name,
            list(vert_counts_mv), list(edge_counts_mv), list(object_counts_mv), group_names)
        engine.send_command_async(command)
        
        final_response = engine.wait_for_response(1)
        
        # Close shared memory in parent process
        for shm in shm_objects:
            shm.close()
        
        if not bool(final_response.get("ok", True)):
            error_msg = final_response.get("error", "Unknown engine error during classify_groups")
            raise RuntimeError(f"classify_groups failed: {error_msg}")

        groups = final_response["groups"]
        
        # --- Extract and apply transforms ---
        group_names = list(groups.keys())
        rots = [Quaternion(groups[name]["rot"]) for name in group_names]
        origins = [tuple(groups[name]["origin"]) for name in group_names]

        # print(origins)
        
        # --- Update pivot positions with actual origins from engine ---
        for i, pivot in enumerate(pivots):
            old_pivot_loc = pivot.location.copy()
            print("Old pivot location:", old_pivot_loc)
            new_pivot_loc = Vector(origins[i]) + pivot.matrix_world.translation
            print("New pivot location:", new_pivot_loc)
            pivot_movement = new_pivot_loc - old_pivot_loc
            print("Pivot movement:", pivot_movement)
            
            # Move all children by the opposite amount to keep them visually in place
            for child in pivot.children:
                child.matrix_world.translation -= pivot_movement
            
            # Now update the pivot location
            pivot.location = new_pivot_loc
        
        # --- Apply transforms to PIVOTS (objects follow via parenting) ---
        _apply_transforms_to_pivots(pivots, rots)
        
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

    # --- Always organize ALL groups using surface types ---
    if all_surface_types:
        all_group_names = list(all_surface_types.keys())
        surface_types = [all_surface_types[name]["surface_type"] for name in all_group_names]
        
        core_group_mgr.update_managed_group_names(all_group_names)
        core_group_mgr.set_groups_synced(all_group_names)
        
        from pivot.surface_manager import get_surface_manager
        get_surface_manager().organize_groups_into_surfaces(
            core_group_mgr.get_managed_group_names_set(), surface_types)


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
    
    # --- Set up pivots BEFORE shared memory setup ---
    parent_groups = [[obj] for obj in mesh_objects]  # Define parent_groups here
    object_names = [obj.name for obj in mesh_objects]
    # Create temporary origins (will be updated by engine)
    temp_origins = [tuple(parent_group[0].matrix_world.translation) for parent_group in parent_groups]
    pivots = _setup_pivots_for_groups_return_empties(parent_groups, object_names, temp_origins, [parent_group[0].matrix_world.translation for parent_group in parent_groups])
    
    # --- Shared memory setup ---
    shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(
        total_verts, total_edges, len(mesh_objects), mesh_groups, pivots)
    
    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv, offsets_mv = count_memory_views
    
    # --- Extract transforms and rotation modes ---
    # parent_groups = [[obj] for obj in mesh_objects]  # Remove duplicate definition
    # all_parent_offsets, all_original_rots = _prepare_object_transforms(
    #     parent_groups, mesh_groups, offsets_mv)
    
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
    
    # --- Update pivot positions with actual origins from engine ---
    for i, pivot in enumerate(pivots):
        old_pivot_loc = pivot.location.copy()
        new_pivot_loc = Vector(origins[i]) + pivots[i].matrix_world.translation
        pivot_movement = new_pivot_loc - old_pivot_loc
        
        # Move all children by the opposite amount to keep them visually in place
        for child in pivot.children:
            child.matrix_world.translation -= pivot_movement
        
        # Now update the pivot location
        pivot.location = new_pivot_loc
    
    # --- Apply transforms to PIVOTS (objects follow via parenting) ---
    _apply_transforms_to_pivots(pivots, rots)