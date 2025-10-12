"""Property Management System

Centralized management of object properties with automatic engine synchronization.
Separation of concerns:
- Public API: setting attributes, scene/object sync entry points
- Engine I/O: command construction and communicator access
- State: expected engine state bookkeeping (engine_state module)
- Checks: helpers to determine if a sync is necessary
"""

import bpy
from typing import Any, Iterable, Optional

from . import engine_state

# Command IDs for engine communication
COMMAND_SET_GROUP_ATTR = 2
COMMAND_SYNC_OBJECT = 3


GROUP_COLLECTION_PROP = "splatter_group_name"

CLASSIFICATION_ROOT_COLLECTION_NAME = "pivot"
CLASSIFICATION_COLLECTION_PROP = "splatter_surface_type"

INTERNAL_ROOT_COLLECTION_NAME = "_splatter_internal"


class PropertyManager:
    """Centralized manager for object properties that handles engine synchronization."""

    def __init__(self) -> None:
        self._engine_communicator: Optional[Any] = None

    # --- Engine I/O helpers -------------------------------------------------

    def _get_engine_communicator(self) -> Optional[Any]:
        """Lazy-initialize and cache the engine communicator."""
        if self._engine_communicator is None:
            try:
                from .engine import get_engine_communicator
                self._engine_communicator = get_engine_communicator()
            except RuntimeError:
                self._engine_communicator = None
        return self._engine_communicator

    # --- Object/group helpers ----------------------------------------------

    def _get_group_name(self, obj: Any) -> Optional[str]:
        """Return the group's name by inspecting classification collections."""
        for coll in getattr(obj, "users_collection", []) or []:
            if getattr(coll, "get", None) is None:
                continue
            group = coll.get(GROUP_COLLECTION_PROP)
            if group:
                return group
        return None

    def get_group_name(self, obj: Any) -> Optional[str]:
        """Public accessor for group names backed by collections."""
        return self._get_group_name(obj)

    # --- Collection helpers ------------------------------------------------

    def _get_or_create_root_collection(self, name: str) -> Optional[Any]:
        scene = getattr(bpy.context, "scene", None)
        if scene is None:
            return None

        root = bpy.data.collections.get(name)
        if root is None:
            root = bpy.data.collections.new(name)
        if scene.collection.children.find(root.name) == -1:
            scene.collection.children.link(root)
        return root

    def _get_or_create_group_collection(self, group_name: str, _root_collection: Optional[Any]) -> Optional[Any]:
        """Return an internal collection used only for tracking group membership."""
        # Ensure the internal root exists to provide user references.
        internal_root = bpy.data.collections.get(INTERNAL_ROOT_COLLECTION_NAME)
        if internal_root is None:
            internal_root = bpy.data.collections.new(INTERNAL_ROOT_COLLECTION_NAME)
            # Add a fake user to prevent deletion.
            internal_root.use_fake_user = True

        for coll in internal_root.children:
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                return coll

        # Create a dedicated hidden collection name to avoid clashing with user data.
        sanitized = group_name.replace('/', '_').replace('\\', '_')
        internal_name = f"_splatter_group_{sanitized}"

        # Reuse an existing internal collection if present.
        existing = bpy.data.collections.get(internal_name)
        if existing is not None and existing.get(GROUP_COLLECTION_PROP) in (None, group_name):
            existing[GROUP_COLLECTION_PROP] = group_name
            if internal_root.children.find(existing.name) == -1:
                internal_root.children.link(existing)
            return existing

        coll = bpy.data.collections.new(internal_name)
        coll[GROUP_COLLECTION_PROP] = group_name
        internal_root.children.link(coll)
        # Add fake user to prevent deletion.
        coll.use_fake_user = True
        return coll

    def _iter_group_objects(self, group_name: str) -> Iterable[Any]:
        for coll in bpy.data.collections:
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                return list(coll.objects)
        return []

    def _unlink_other_group_collections(self, obj: Any, keep: Optional[Any]) -> None:
        to_unlink: list[Any] = []
        for coll in getattr(obj, "users_collection", []) or []:
            if coll.get(GROUP_COLLECTION_PROP) and coll is not keep:
                to_unlink.append(coll)
        for coll in to_unlink:
            try:
                coll.objects.unlink(obj)
            except RuntimeError:
                pass

    def _assign_surface_collection(self, obj: Any, surface_value: Any) -> None:
        surface_key = str(surface_value)
        root = self._get_or_create_root_collection(CLASSIFICATION_ROOT_COLLECTION_NAME)
        if root is None:
            return

        target = None
        for coll in root.children:
            if coll.get(CLASSIFICATION_COLLECTION_PROP) == surface_key:
                target = coll
                break

        if target is None:
            name = surface_key
            existing = bpy.data.collections.get(name)
            if existing is not None and root.children.find(existing.name) == -1:
                target = existing
            else:
                target = bpy.data.collections.new(name)
            if root.children.find(target.name) == -1:
                root.children.link(target)
            target[CLASSIFICATION_COLLECTION_PROP] = surface_key

        # Unlink from other classification collections.
        to_unlink: list[Any] = []
        for coll in getattr(obj, "users_collection", []) or []:
            if coll.get(CLASSIFICATION_COLLECTION_PROP) and coll is not target:
                to_unlink.append(coll)
        for coll in to_unlink:
            try:
                coll.objects.unlink(obj)
            except RuntimeError:
                pass

        if target not in obj.users_collection:
            target.objects.link(obj)

    def set_attribute(self, obj: Any, attr_name: str, value: Any, update_group: bool = True, update_engine: bool = True) -> bool:
        """Set an attribute for an object with optional group and engine updates.

        - Converts engine_value to Blender's stored value when needed (e.g., enums).
        - Optionally emits a single group-level engine command before updating Blender state.
        - Updates expected engine state for the group to keep future diffs minimal.
        """
        if not hasattr(obj, 'classification'):
            return False

        group_name = self._get_group_name(obj)

        # Handle group update with engine sync
        if update_group and update_engine and group_name:
            if not self._send_group_attribute_command(group_name, attr_name, value):
                return False

        # Update the object's property
        if hasattr(obj, 'classification') and getattr(obj.classification, attr_name, None) != value:
            setattr(obj.classification, attr_name, value)

        if attr_name == 'surface_type':
            self._assign_surface_collection(obj, value)

        # Update group properties if requested
        if update_group and group_name:
            self._update_group_attribute(obj, attr_name, value, value)
            self._update_engine_state(group_name, attr_name, value)
        elif update_engine and group_name:
            self._update_engine_state(group_name, attr_name, value)

        return True

    def _send_group_attribute_command(self, group_name: str, attr_name: str, value: Any) -> bool:
        """Send a single command to engine to set a group's attribute."""
        engine = self._get_engine_communicator()
        if not engine:
            return False

        try:
            command = {
                "id": COMMAND_SET_GROUP_ATTR,
                "op": "set_group_attr",
                "group_name": group_name,
                "attr": attr_name,
                "value": value
            }
            response = engine.send_command(command)
            if "ok" not in response or not response["ok"]:
                print(f"Failed to update engine group {attr_name}: {response.get('error', 'Unknown error')}")
                return False
            return True
        except Exception as e:
            print(f"Error updating engine group {attr_name}: {e}")
            return False

    def set_group_name(self, obj: Any, group_name: str, root_collection: Optional[Any] = None) -> bool:
        """Set group name for an object."""
        coll = self._get_or_create_group_collection(group_name, root_collection)
        if coll is None:
            return False

        if coll not in obj.users_collection:
            coll.objects.link(obj)

        self._unlink_other_group_collections(obj, coll)

        return True

    def _update_engine_state(self, group_name: str, attr_name: str, value: Any) -> None:
        """Update the expected engine state for a group attribute."""
        engine_state._engine_expected_state.setdefault(group_name, {})[attr_name] = value

    def _update_group_attribute(self, source_obj: Any, attr_name: str, blender_value: Any, engine_value: Any) -> None:
        """Update Blender properties for all members of the source object's group."""
        group_name = self._get_group_name(source_obj)
        if not group_name:
            return

        # Update all other objects in the group (skip the source object)
        for obj in self._iter_group_objects(group_name):
            if obj is source_obj:
                continue
            if not hasattr(obj, 'classification'):
                continue
            if getattr(obj.classification, attr_name, None) != blender_value:
                setattr(obj.classification, attr_name, blender_value)

    def sync_object_properties(self, obj: Any) -> int:
        """Sync all properties that need synchronization for an object.

        Returns number of attributes actually synchronized.
        """
        synced_count = 0
        for attr_name in get_syncable_properties():
            if self.needs_attribute_sync(obj, attr_name):
                if self.sync_attribute_with_engine(obj, attr_name):
                    synced_count += 1
        return synced_count

    def sync_attribute_with_engine(self, obj: Any, attr_name: str) -> bool:
        """Sync a single object's attribute to the engine (by group)."""
        group_name = self._get_group_name(obj)
        if not group_name:
            return False

        engine = self._get_engine_communicator()
        if not engine:
            return False

        try:
            value = getattr(obj.classification, attr_name)
            command = {
                "id": COMMAND_SYNC_OBJECT,
                "op": "set_group_attr",
                "group_name": group_name,
                "attr": attr_name,
                "value": value
            }

            response = engine.send_command(command)
            if response.get("ok"):
                self._update_engine_state(group_name, attr_name, value)
                return True
            else:
                print(f"Failed to sync {obj.name} {attr_name}: {response.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"Error syncing {obj.name} {attr_name}: {e}")

        return False

    def needs_attribute_sync(self, obj: Any, attr_name: str) -> bool:
        """Return True if an object's attribute differs from expected engine state."""
        classification = getattr(obj, 'classification', None)
        if classification is None or not hasattr(classification, attr_name):
            return False

        # Only sync objects that have been assigned a group
        group_name = self._get_group_name(obj)
        if not group_name:
            return False

        try:
            current_value = getattr(classification, attr_name)
            expected_value = engine_state._engine_expected_state.get(group_name, {}).get(attr_name)
            return expected_value is not None and current_value != expected_value
        except (ValueError, AttributeError):
            return False

    def needs_sync(self, obj: Any) -> bool:
        """Return True if any syncable property on the object needs synchronization."""
        for attr_name in get_syncable_properties():
            if self.needs_attribute_sync(obj, attr_name):
                return True
        return False

    def sync_scene_after_undo(self, scene: Any) -> tuple[int, int]:
        """Deduplicated group/attribute sync for undo/redo passes.

        Returns (synced_pairs_count, touched_groups_count).
        """
        props = get_syncable_properties()
        print(f"Syncable properties: {props}")
        synced_pairs: set[tuple[str, str]] = set()
        groups_touched: set[str] = set()

        for obj in scene.objects:
            group_name = self._get_group_name(obj)
            if not group_name:
                continue

            for attr_name in props:
                pair = (group_name, attr_name)
                if pair in synced_pairs:
                    continue

                # If expected state is missing for this group/attr, seed it from current value.
                expected = engine_state._engine_expected_state.get(group_name, {}).get(attr_name)
                needs = expected is None or self.needs_attribute_sync(obj, attr_name)
                if needs and self.sync_attribute_with_engine(obj, attr_name):
                    synced_pairs.add(pair)
                    groups_touched.add(group_name)

        return (len(synced_pairs), len(groups_touched))


_SYNCABLE_PROPS_CACHE: Optional[list[str]] = None

def get_syncable_properties() -> list[str]:
    """Return the list of syncable properties with safe, lazy caching.

    Prefers ObjectAttributes.__annotations__ when available; otherwise falls back
    to checking for known runtime properties. Avoids caching empty results so
    late-initialized properties (post-register) are eventually discovered.
    """
    global _SYNCABLE_PROPS_CACHE
    if _SYNCABLE_PROPS_CACHE:
        return list(_SYNCABLE_PROPS_CACHE)

    props: list[str] = []
    try:
        from .classes import ObjectAttributes
        annotations = getattr(ObjectAttributes, '__annotations__', {}) or {}
        if annotations:
            props = [n for n in annotations if n != 'group_name']
        else:
            # Fallback for Blender runtime-defined properties (no annotations)
            for name in ('surface_type',):
                if hasattr(ObjectAttributes, name):
                    props.append(name)
    except Exception:
        # If classes can't be imported yet, return empty and try again later
        return []

    if props:
        _SYNCABLE_PROPS_CACHE = props
    return props


# Global instance
_property_manager = PropertyManager()

def get_property_manager() -> PropertyManager:
    """Get the global property manager instance."""
    return _property_manager
