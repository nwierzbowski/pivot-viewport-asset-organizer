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

def _apply_transforms_to_pivots(pivots, origins, rots, cogs):
    """Apply position and rotation transforms to pivots.
    Updates pivot positions with origins, then applies rotations by modifying children's matrix_local."""

    for i, pivot in enumerate(pivots):
        rotation_matrix = rots[i].to_matrix().to_4x4()
        
        target_origin = pivot.matrix_world.translation + Vector(cogs[i]) + rotation_matrix @ (Vector(origins[i]) - Vector(cogs[i]))

        for child in pivot.children:
            child.matrix_local = Matrix.Translation(rotation_matrix @ (Vector(cogs[i]) - Vector(origins[i]))) @ rotation_matrix @ Matrix.Translation(-Vector(cogs[i])) @ child.matrix_local

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


def _standardize_synced_groups(engine, synced_group_names, surface_context):
    """Reclassify cached groups without sending mesh data."""

    if not synced_group_names:
        return {}

    command = engine.build_standardize_synced_groups_command(synced_group_names, surface_context)
    final_response = _send_engine_command_and_get_response(engine, command)
    return final_response.get("groups", {})

def standardize_groups(list selected_objects, str origin_method, str surface_context):
    """Pro Edition: Classify selected groups via engine."""

    mesh_groups, full_groups, group_names, total_verts, total_edges, total_objects, pivots, synced_group_names, synced_pivots = selection_utils.aggregate_object_groups(selected_objects)
    core_group_mgr = group_manager.get_group_manager()

    engine = get_engine_communicator()
    new_group_results = {}
    transformed_group_names = []

    if group_names:
        shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(
            total_verts, total_edges, total_objects, mesh_groups, pivots)

        verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
        vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views

        command = engine.build_standardize_groups_command(
            verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name,
            list(vert_counts_mv), list(edge_counts_mv), list(object_counts_mv), group_names, surface_context)

        final_response = _send_engine_command_and_get_response(engine, command)

        _close_shared_memory_segments(shm_objects)

        new_group_results = final_response["groups"]
        transformed_group_names = list(new_group_results.keys())

        group_membership_snapshot = engine_state.build_group_membership_snapshot(full_groups, transformed_group_names)
        engine_state.update_group_membership_snapshot(group_membership_snapshot, replace=False)

    synced_group_results = _standardize_synced_groups(engine, synced_group_names, surface_context)

    all_group_results = {**new_group_results, **synced_group_results}
    all_transformed_group_names = list(all_group_results.keys())

    if all_transformed_group_names:
        all_rots = [Quaternion(all_group_results[name]["rot"]) for name in all_transformed_group_names]
        all_origins = [tuple(all_group_results[name]["origin"]) for name in all_transformed_group_names]
        all_cogs = [tuple(all_group_results[name]["cog"]) for name in all_transformed_group_names]

        if origin_method == "BASE":
            all_new_origins = all_origins
        else:
            all_new_origins = all_cogs

        pivot_lookup = {group_names[i]: pivots[i] for i in range(len(group_names))}
        pivot_lookup.update({synced_group_names[i]: synced_pivots[i] for i in range(len(synced_group_names))})
        all_pivots = []
        for name in all_transformed_group_names:
            pivot = pivot_lookup.get(name)
            if pivot is None:
                print(f"Warning: Pivot not found for group '{name}'")
            all_pivots.append(pivot)

        _apply_transforms_to_pivots(all_pivots, all_new_origins, all_rots, all_cogs)

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


def _get_standardize_results(list objects, str surface_context="AUTO"):
    """
    Helper function to get standardization results from the engine.
    Returns mesh_objects, rots, origins, cogs
    """
    if not objects:
        return [], [], [], []
    
    # Validation: STANDARD edition only supports single object
    if len(objects) > 1 and not edition_utils.is_pro_edition():
        raise RuntimeError(f"STANDARD edition only supports single object classification, got {len(objects)}")
    
    # Filter to mesh objects only
    mesh_objects = [obj for obj in objects if obj.type == 'MESH']
    if not mesh_objects:
        return [], [], [], []
    
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
        return [], [], [], []
    
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
        list(vert_counts_mv), list(edge_counts_mv), [obj.name for obj in mesh_objects], surface_context)
    engine.send_command_async(command)
    
    final_response = engine.wait_for_response(1)
    
    # Close shared memory in parent process
    _close_shared_memory_segments(shm_objects)
    
    if not bool(final_response.get("ok", True)):
        error_msg = final_response.get("error", "Unknown engine error during classify_objects")
        raise RuntimeError(f"classify_objects failed: {error_msg}")
    
    # --- Extract engine results ---
    # Engine returns results as a dict keyed by object name
    results = final_response.get("results", {})
    rots = [Quaternion(results[obj.name]["rot"]) for obj in mesh_objects if obj.name in results]
    origins = [tuple(results[obj.name]["origin"]) for obj in mesh_objects if obj.name in results]
    cogs = [tuple(results[obj.name]["cog"]) for obj in mesh_objects if obj.name in results]
    
    return mesh_objects, rots, origins, cogs



def standardize_object_origins(list objects, str origin_method, str surface_context="AUTO"):
    mesh_objects, rots, origins, cogs = _get_standardize_results(objects, surface_context)
    if not mesh_objects:
        return
    new_origins = []

    if (origin_method == "BASE"):
        new_origins = origins
    else:
        new_origins = cogs

    for i, obj in enumerate(mesh_objects):
        if i < len(origins) and i < len(cogs):

            origin_vector = obj.matrix_world.translation + Vector(new_origins[i])
            set_origin_and_preserve_children(obj, origin_vector)
            bpy.context.scene.cursor.location = obj.matrix_world.translation
    

def standardize_object_rotations(list objects):
    mesh_objects, rots, origins, cogs = _get_standardize_results(objects)
    if not mesh_objects:
        return
    for i, obj in enumerate(mesh_objects):
        if i < len(rots) and i < len(cogs):
            rot = rots[i]
            cog = obj.matrix_world.translation + Vector(cogs[i])
            rotation_matrix = rot.to_matrix().to_4x4()
            transform = Matrix.Translation(cog) @ rotation_matrix @ Matrix.Translation(-cog)
            obj.matrix_world = transform @ obj.matrix_world