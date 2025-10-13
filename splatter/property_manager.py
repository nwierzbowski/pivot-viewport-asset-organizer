"""Property Management System

Centralized management of object properties with automatic engine synchronization.
Separation of concerns:
- Public API: setting attributes, scene/object sync entry points
- Engine I/O: command construction and communicator access
- State: expected engine state bookkeeping (engine_state module)
- Checks: helpers to determine if a sync is necessary
"""

import bpy
from typing import Any, Dict, Iterable, Optional

from . import engine_state

# Command IDs for engine communication
COMMAND_SET_GROUP_ATTR = 2
COMMAND_SYNC_OBJECT = 3
COMMAND_SET_GROUP_CLASSIFICATIONS = 4


GROUP_COLLECTION_PROP = "splatter_group_name"

CLASSIFICATION_ROOT_COLLECTION_NAME = "pivot"
CLASSIFICATION_COLLECTION_PROP = "splatter_surface_type"


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

    def _iter_child_collections(self, root: Any) -> Iterable[Any]:
        stack = list(getattr(root, "children", []) or [])
        while stack:
            coll = stack.pop()
            yield coll
            stack.extend(list(getattr(coll, "children", []) or []))

    def _collection_contains_object(self, coll: Any, obj: Any) -> bool:
        try:
            if coll.objects.find(obj.name) != -1:
                return True
        except (AttributeError, ReferenceError):
            return False

        for child in getattr(coll, "children", []) or []:
            if self._collection_contains_object(child, obj):
                return True
        return False

    def _find_top_collection_for_object(self, obj: Any, root_collection: Any) -> Optional[Any]:
        if root_collection is None:
            return None

        for child in getattr(root_collection, "children", []) or []:
            if self._collection_contains_object(child, obj):
                return child
        return None

    def _is_descendant_of(self, candidate: Any, root: Any) -> bool:
        if candidate is None or root is None or candidate == root:
            return False

        for coll in self._iter_child_collections(root):
            if coll == candidate:
                return True
        return False

    def _rename_collection(self, coll: Any, new_name: str) -> None:
        if getattr(coll, "name", None) == new_name:
            return

        existing = bpy.data.collections.get(new_name)
        if existing is not None and existing is not coll:
            return
        coll.name = new_name

    def _get_group_collection_for_object(self, obj: Any, group_name: Optional[str]) -> Optional[Any]:
        if not group_name:
            return None

        for coll in getattr(obj, "users_collection", []) or []:
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                return coll
        return None

    def _ensure_collection_link(self, parent: Any, child: Any) -> None:
        if parent is None or child is None:
            return

        children = getattr(parent, "children", None)
        if children is None:
            return

        if children.find(child.name) == -1:
            children.link(child)

    def _get_or_create_surface_collection(self, pivot_root: Any, surface_key: str) -> Optional[Any]:
        if pivot_root is None:
            return None

        for coll in pivot_root.children:
            if coll.get(CLASSIFICATION_COLLECTION_PROP) == surface_key:
                return coll

        # Attempt to reuse existing collection by name if available.
        existing = bpy.data.collections.get(surface_key)
        if existing is not None:
            self._ensure_collection_link(pivot_root, existing)
            existing[CLASSIFICATION_COLLECTION_PROP] = surface_key
            return existing

        surface_coll = bpy.data.collections.new(surface_key)
        surface_coll[CLASSIFICATION_COLLECTION_PROP] = surface_key
        pivot_root.children.link(surface_coll)
        return surface_coll

    def _get_or_create_group_collection(self, obj: Any, group_name: str, root_collection: Optional[Any]) -> Optional[Any]:
        """Return a collection under root_collection used for tracking group membership."""
        if root_collection is None:
            return None

        # Reuse any existing child collection tagged with this group.
        for coll in self._iter_child_collections(root_collection):
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                return coll

        # If the root collection itself carries the group tag, reuse it.
        if root_collection.get(GROUP_COLLECTION_PROP) == group_name:
            return root_collection

        # Collection-based groups: reuse the top-level collection that currently owns the object.
        if group_name.endswith("_C"):
            top_coll = self._find_top_collection_for_object(obj, root_collection)
            if top_coll is None:
                top_coll = bpy.data.collections.new(group_name)
                root_collection.children.link(top_coll)
            else:
                self._rename_collection(top_coll, group_name)

            top_coll[GROUP_COLLECTION_PROP] = group_name
            return top_coll

        # Parent-based groups: create (or reuse) a dedicated collection under the root.
        existing_named = bpy.data.collections.get(group_name)
        if existing_named is not None and self._is_descendant_of(existing_named, root_collection):
            existing_named[GROUP_COLLECTION_PROP] = group_name
            return existing_named

        coll = bpy.data.collections.new(group_name)
        coll[GROUP_COLLECTION_PROP] = group_name
        root_collection.children.link(coll)
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
        pivot_root = self._get_or_create_root_collection(CLASSIFICATION_ROOT_COLLECTION_NAME)
        if pivot_root is None:
            return

        group_name = self._get_group_name(obj)
        group_collection = self._get_group_collection_for_object(obj, group_name)

        # Fallback in the unlikely event the object is missing its group collection.
        if group_collection is None:
            fallback_name = group_name or surface_key
            group_collection = bpy.data.collections.get(fallback_name)
            if group_collection is None:
                group_collection = bpy.data.collections.new(fallback_name)
            if group_collection not in obj.users_collection:
                group_collection.objects.link(obj)
            group_collection[GROUP_COLLECTION_PROP] = group_name or fallback_name

        surface_collection = self._get_or_create_surface_collection(pivot_root, surface_key)
        if surface_collection is None:
            return

        # Link the group collection under the correct surface classification branch.
        self._ensure_collection_link(surface_collection, group_collection)

        # Ensure the group collection's metadata reflects its latest surface type and
        # that it is not linked under any other surface containers.
        group_collection[CLASSIFICATION_COLLECTION_PROP] = surface_key

        for coll in pivot_root.children:
            if coll is surface_collection:
                continue
            children = getattr(coll, "children", None)
            if children is None:
                continue
            if children.find(group_collection.name) != -1:
                children.unlink(group_collection)

    def collect_group_classifications(self) -> Dict[str, int]:
        """Collect current group -> surface classification mapping from Blender collections."""
        result: Dict[str, int] = {}
        pivot_root = bpy.data.collections.get(CLASSIFICATION_ROOT_COLLECTION_NAME)
        if pivot_root is None:
            return result

        for surface_coll in getattr(pivot_root, "children", []) or []:
            surface_value = surface_coll.get(CLASSIFICATION_COLLECTION_PROP)
            if surface_value is None:
                continue

            try:
                surface_int = int(surface_value)
            except (TypeError, ValueError):
                continue

            for group_coll in getattr(surface_coll, "children", []) or []:
                group_name = group_coll.get(GROUP_COLLECTION_PROP)
                if not group_name:
                    continue
                result[group_name] = surface_int

        return result

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

    def sync_group_classifications(self, group_surface_map: Dict[str, Any]) -> bool:
        """Send a batch classification update to the engine."""
        if not group_surface_map:
            return True

        engine = self._get_engine_communicator()
        if not engine:
            return False

        classifications_payload = []
        normalized_map: Dict[str, int] = {}
        for name, value in group_surface_map.items():
            try:
                surface_int = int(value)
            except (TypeError, ValueError):
                continue
            classifications_payload.append({
                "group_name": name,
                "surface_type": surface_int
            })
            normalized_map[name] = surface_int

        if not classifications_payload:
            return True

        try:
            command = {
                "id": COMMAND_SET_GROUP_CLASSIFICATIONS,
                "op": "set_group_classifications",
                "classifications": classifications_payload
            }
            response = engine.send_command(command)
            if not response.get("ok", False):
                error = response.get("error", "Unknown error")
                print(f"Failed to update group classifications: {error}")
                return False

            for group_name, surface_int in normalized_map.items():
                self._update_engine_state(group_name, "surface_type", surface_int)
            return True
        except Exception as exc:
            print(f"Error sending group classifications: {exc}")
            return False

    def set_group_name(self, obj: Any, group_name: str, root_collection: Optional[Any] = None) -> bool:
        """Set group name for an object."""
        coll = self._get_or_create_group_collection(obj, group_name, root_collection)
        if coll is None:
            return False

        if coll not in obj.users_collection:
            coll.objects.link(obj)

        if root_collection is not None and root_collection is not coll:
            try:
                root_collection.objects.unlink(obj)
            except RuntimeError:
                pass

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
            props = list(annotations)
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
