# Depsgraph Update Handlers
# ---------------------------
# Handles Blender depsgraph updates for detecting scene changes and maintaining sync state.

import bpy
from bpy.app.handlers import persistent

from . import engine_state
from .lib import group_manager
import time

# Cache of each object's last-known scale to detect transform-only edits quickly.
_previous_scales: dict[str, tuple[float, float, float]] = {}
# Cache of each object's last-known rotation to detect rotation changes.
_previous_rotations: dict[str, tuple[float, float, float, float]] = {}


@persistent
def on_depsgraph_update(scene, depsgraph):
    """Orchestrate all depsgraph update handlers in guaranteed order."""
    start_time = time.time()
    if engine_state._is_performing_classification:
        engine_state._is_performing_classification = False
    else:
        detect_collection_hierarchy_changes(scene, depsgraph)
        unsync_mesh_changes(scene, depsgraph)
    enforce_colors(scene, depsgraph)
    end_time = time.time()
    print(f"on_depsgraph_update took {1000 * (end_time - start_time):.4f} milliseconds")


def detect_collection_hierarchy_changes(scene, depsgraph):
    """Detect changes in collection hierarchy and mark affected groups as out-of-sync with the engine."""
    group_mgr = group_manager.get_group_manager()
    
    current_snapshot = group_mgr.get_group_membership_snapshot()
    expected_snapshot = engine_state.get_group_membership_snapshot()
    for group_name, expected_members in expected_snapshot.items():
        current_members = current_snapshot.get(group_name, set())
        if expected_members != current_members:
            group_mgr.set_group_unsynced(group_name)


def enforce_colors(scene, depsgraph):
    """Enforce correct color tags for group collections based on sync state."""
    group_mgr = group_manager.get_group_manager()
    group_mgr.update_orphaned_groups()
    group_mgr.update_colors()


def unsync_mesh_changes(scene, depsgraph):
    """Detect mesh and transform changes on selected objects and mark groups as unsynced."""
    global _previous_scales, _previous_rotations
    
    group_mgr = group_manager.get_group_manager()

    # Get all selected mesh objects first (quick operation)
    all_selected_mesh = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    all_selected_mesh_set = set(all_selected_mesh)  # For O(1) lookup
    
    if not all_selected_mesh:
        return  # No selected objects, nothing to do
    
    # Get managed collections info (fast, no full snapshot yet)
    orphaned_groups = set(group_mgr.get_orphaned_groups())  # Convert to set for O(1) lookups
    managed_group_names = group_mgr.get_sync_state_keys()  # Already returns a set
    
    selected_objects = []
    obj_to_group = {}
    
    # Iterate managed collections to find selected objects (avoids checking all 220 objects)
    for group_name in managed_group_names:
        if group_name in orphaned_groups:
            continue
        
        # Get the collection
        coll = bpy.data.collections.get(group_name)
        if not coll:
            continue
        
        # Check only objects in this collection against selected set (O(1) lookups)
        for obj in coll.objects:
            if obj in all_selected_mesh_set:
                selected_objects.append(obj)
                obj_to_group[obj] = group_name
    
    if not selected_objects:
        return  # No selected objects in managed collections
    
    # Only build snapshots if we have selected objects to process
    expected_snapshot = engine_state.get_group_membership_snapshot()
    current_snapshot = group_mgr.get_group_membership_snapshot()
    
    # Build reverse lookup for O(1) matching: update.id.original -> obj
    id_to_obj = {}
    for obj in selected_objects:
        id_to_obj[id(obj)] = obj
        id_to_obj[id(obj.data)] = obj

    # Main processing loop
    for update in depsgraph.updates:
        if not (update.is_updated_geometry or update.is_updated_transform):
            continue

        # O(1) lookup instead of O(m) loop
        obj = id_to_obj.get(id(update.id.original))
        if obj is None:
            continue

        group_name = obj_to_group.get(obj)
        # Group name is guaranteed to be valid since we filtered selected_objects

        expected_members = expected_snapshot.get(group_name)
        current_members = current_snapshot.get(group_name, set())
        member_count = len(expected_members) if expected_members is not None else len(current_members)

        current_scale = tuple(obj.scale)
        prev_scale = _previous_scales.get(obj.name)
        scale_changed = prev_scale is not None and current_scale != prev_scale

        current_rotation = tuple(obj.rotation_quaternion)
        prev_rotation = _previous_rotations.get(obj.name)
        rotation_changed = prev_rotation is not None and current_rotation != prev_rotation

        should_mark_unsynced = (
            expected_members is None
            or update.is_updated_geometry
            or scale_changed
            or rotation_changed
            or (update.is_updated_transform and member_count > 1)
        )

        if should_mark_unsynced:
            group_mgr.set_group_unsynced(group_name)

        # Update scale and rotation caches for next handler invocation
        _previous_scales[obj.name] = current_scale
        _previous_rotations[obj.name] = current_rotation

def clear_previous_scales():
    """Clear the scale and rotation caches used for detecting transform changes."""
    global _previous_scales, _previous_rotations
    _previous_scales.clear()
    _previous_rotations.clear()


def on_group_name_changed(collection, group_mgr):
    """Callback for when a managed group's name changes.
    
    Args:
        collection: The collection whose name changed
        group_mgr: The GroupManager instance
    """
    name_tracker = group_mgr.get_name_tracker()
    
    old_name = name_tracker.get(collection)
    new_name = collection.name

    if old_name and old_name != new_name:
        # Set the collection color to none to indicate it's orphaned
        collection.color_tag = 'NONE'
    
    # Update the tracker with the new name
    name_tracker[collection] = new_name
    