# Copyright (C) 2025 [Nicholas Wierzbowski/Elbo Studio]

# This file is part of the Pivot Bridge for Blender.

# The Pivot Bridge for Blender is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses>.

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
from pivot.surface_manager import get_surface_manager
from multiprocessing.shared_memory import SharedMemory

# Collection metadata keys
GROUP_COLLECTION_PROP = "pivot_group_name"
CLASSIFICATION_ROOT_COLLECTION_NAME = "Pivot"
CLASSIFICATION_COLLECTION_PROP = "pivot_surface_type"

def _apply_transforms_to_pivots(pivots, origins, rots, cogs, bint origin_method_is_base):
    """Apply position and rotation transforms to pivots using the chosen origin method."""

    for i, pivot in enumerate(pivots):
        if pivot is None:
            continue

        is_base = group_manager.get_group_manager().was_object_last_transformed_using_base(pivot)
        if not is_base:
            pivot.matrix_world.translation -= Vector(cogs[i])
            
        origin_vector = Vector(origins[i]) if origin_method_is_base else Vector(cogs[i])
        pivot_world_rot = pivot.matrix_world.to_quaternion()
        world_rot = pivot_world_rot @ rots[i]
        rotation_matrix = world_rot.to_matrix().to_4x4()

        world_cog = pivot.matrix_world @ Vector(cogs[i])
        world_origin = pivot.matrix_world @ origin_vector
        target_origin = world_cog + rotation_matrix @ (world_origin - world_cog)

        local_cog = Vector(cogs[i])
        local_origin = origin_vector
        local_rotation_matrix = rots[i].to_matrix().to_4x4()

        pre_rotate = Matrix.Translation(local_rotation_matrix @ (local_cog - local_origin)) @ local_rotation_matrix
        post_translate = Matrix.Translation(-local_cog)
        for child in pivot.children:
            child.matrix_local = pre_rotate @ post_translate @ child.matrix_local

        pivot.matrix_world.translation = target_origin

def set_origin_and_preserve_children(obj, new_origin_local):
    """Move object origin to new_origin_world while preserving visual placement of mesh and children."""
    old_matrix = obj.matrix_world.copy()
    print(new_origin_local)
    # Rotate new_origin_local by the inverse of the world matrix rotation to get local space
    local_new_origin = old_matrix.to_3x3().inverted() @ new_origin_local
    new_world_pos = old_matrix.translation + new_origin_local
    correction = Matrix.Translation(-local_new_origin)

    # Apply correction to mesh if it exists
    if hasattr(obj, 'data') and hasattr(obj.data, 'transform'):
        obj.data.transform(correction)

    # Update world location and fix children parenting
    obj.matrix_world.translation = new_world_pos
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


def _build_group_surface_contexts(group_names, surface_context, classification_map=None):
    """Build per-group surface context strings, honoring AUTO overrides with stored classifications."""

    if not group_names:
        return []

    contexts = []
    auto_context = surface_context == "AUTO"
    map_to_use = classification_map
    if auto_context and map_to_use is None:
        map_to_use = get_surface_manager().collect_group_classifications()
    if map_to_use is None:
        map_to_use = {}

    for name in group_names:
        if auto_context and name in map_to_use:
            surface_type_int = map_to_use[name]
            if surface_type_int in (0, 1, 2):
                contexts.append(str(surface_type_int))
            else:
                contexts.append("AUTO")
        else:
            # surface_context is already in the correct format (AUTO, 0, 1, 2)
            if surface_context in ("AUTO", "0", "1", "2"):
                contexts.append(surface_context)
            else:
                contexts.append("AUTO")  # default to AUTO

    return contexts


def _standardize_synced_groups(engine, synced_group_names, surface_contexts):
    """Reclassify cached groups without sending mesh data."""

    if not synced_group_names:
        return {}

    command = engine.build_standardize_synced_groups_command(synced_group_names, surface_contexts)
    final_response = _send_engine_command_and_get_response(engine, command)
    return final_response.get("groups", {})

def standardize_groups(list selected_objects, str origin_method, str surface_context):
    """Pro Edition: Classify selected groups via engine."""

    mesh_groups, full_groups, group_names, total_verts, total_edges, total_objects, pivots, synced_group_names, synced_pivots = selection_utils.aggregate_object_groups(selected_objects)
    core_group_mgr = group_manager.get_group_manager()
    origin_method_is_base = origin_method == "BASE"

    engine = get_engine_communicator()
    new_group_results = {}
    transformed_group_names = []

    #Retain old classifications for user correction support
    classification_map = None
    if surface_context == "AUTO" and (group_names or synced_group_names):
        classification_map = get_surface_manager().collect_group_classifications()

    if group_names:
        shm_objects, shm_names, count_memory_views = shm_utils.create_data_arrays(
            total_verts, total_edges, total_objects, mesh_groups, pivots, True)

        verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
        vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views

        surface_contexts = _build_group_surface_contexts(group_names, surface_context, classification_map)
        command = engine.build_standardize_groups_command(
            verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name,
            list(vert_counts_mv), list(edge_counts_mv), list(object_counts_mv), group_names, surface_contexts)
        print("Pre engine shared memory checks:")
        for shm in shm_objects:
            debug_shm(shm)

        final_response = _send_engine_command_and_get_response(engine, command)
        print("Post engine shared memory checks:")
        for shm in shm_objects:
            debug_shm(shm)

        _close_shared_memory_segments(shm_objects)
        # print("Post close shared memory checks:")
        # for shm in shm_objects:
        #     debug_shm(shm)

        new_group_results = final_response["groups"]
        transformed_group_names = list(new_group_results.keys())

        group_membership_snapshot = engine_state.build_group_membership_snapshot(full_groups, transformed_group_names)
        engine_state.update_group_membership_snapshot(group_membership_snapshot, replace=False)

    synced_surface_contexts = _build_group_surface_contexts(synced_group_names, surface_context, classification_map)
    synced_group_results = _standardize_synced_groups(engine, synced_group_names, synced_surface_contexts)

    all_group_results = {**new_group_results, **synced_group_results}
    all_transformed_group_names = list(all_group_results.keys())

    if all_transformed_group_names:
        all_rots = [Quaternion(all_group_results[name]["rot"]) for name in all_transformed_group_names]
        all_origins = [tuple(all_group_results[name]["origin"]) for name in all_transformed_group_names]
        all_cogs = [tuple(all_group_results[name]["cog"]) for name in all_transformed_group_names]

        pivot_lookup = {group_names[i]: pivots[i] for i in range(len(group_names))}
        pivot_lookup.update({synced_group_names[i]: synced_pivots[i] for i in range(len(synced_group_names))})
        all_pivots = []
        for name in all_transformed_group_names:
            pivot = pivot_lookup.get(name)
            if pivot is None:
                print(f"Warning: Pivot not found for group '{name}'")
            all_pivots.append(pivot)

        _apply_transforms_to_pivots(all_pivots, all_origins, all_rots, all_cogs, origin_method_is_base)
        core_group_mgr.set_groups_last_origin_method_base(all_transformed_group_names, origin_method_is_base)

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
        
        # Pass as parallel lists with verified alignment to avoid swapping
        get_surface_manager().organize_groups_into_surfaces(all_group_names, surface_types)

def debug_shm(shm):
    print("=== Shared Memory Debug ===")
    print("Name:", repr(shm.name))
    print("Size:", shm.size)

    # Try re-open to confirm existence
    try:
        test = SharedMemory(shm.name)
        print("Re-open test: OK")
        test.close()
    except Exception as e:
        print("Re-open test FAILED:", e)

    # Show content sample
    print("First bytes:", bytes(shm.buf[:16]).hex())
    print("============================")

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
        total_verts, total_edges, len(mesh_objects), mesh_groups, [], False)  # No pivots for objects
    
    verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name = shm_names
    vert_counts_mv, edge_counts_mv, object_counts_mv = count_memory_views
    
    # --- Engine communication: unified array format ---
    # Engine will validate that multiple objects are only used in PRO edition
    engine = get_engine_communicator()
    # Map surface_context to engine-expected string
    print(f"Standardize surface context: {surface_context}")
    if surface_context in ("AUTO", "0", "1", "2"):
        engine_surface_context = surface_context
    else:
        engine_surface_context = "AUTO"
    surface_contexts = [engine_surface_context] * len(mesh_objects)
    command = engine.build_standardize_objects_command(
        verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name,
        list(vert_counts_mv), list(edge_counts_mv), [obj.name for obj in mesh_objects], surface_contexts)
    print("Pre engine shared memory checks:")
    for shm in shm_objects:
        debug_shm(shm)
    
    engine.send_command_async(command)
    
    final_response = engine.wait_for_response(1)
    
    print("Post engine shared memory checks:")
    for shm in shm_objects:
        debug_shm(shm)

    _close_shared_memory_segments(shm_objects)
    # print("Post close shared memory checks:")
    # for shm in shm_objects:
    #     debug_shm(shm)
    
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

            # origin_vector = obj.matrix_world.translation + 
            set_origin_and_preserve_children(obj, Vector(new_origins[i]))
            bpy.context.scene.cursor.location = obj.matrix_world.translation
    

def standardize_object_rotations(list objects):
    mesh_objects, rots, origins, cogs = _get_standardize_results(objects)
    if not mesh_objects:
        return
    for i, obj in enumerate(mesh_objects):
        if i < len(rots) and i < len(cogs):
            rot = rots[i]
            cog = Vector(cogs[i])
            rotation_matrix = rot.to_matrix().to_4x4()
            transform = Matrix.Translation(obj.matrix_world.translation + cog) @ rotation_matrix @ Matrix.Translation(-obj.matrix_world.translation - cog) @ obj.matrix_world
            obj.matrix_world = transform