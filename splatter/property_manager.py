"""Property management glue between Blender collections and the C++ engine.

Responsibilities:
- Track group metadata stored on Blender collections.
- Keep the expected engine state in sync with Blender edits.
- Provide a small, explicit API for callers to manage sync status.
"""

import bpy
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, Optional, Set

from . import engine_state

# Command IDs for engine communication
COMMAND_SET_GROUP_CLASSIFICATIONS = 4

# Property keys for collection metadata
GROUP_COLLECTION_PROP = "splatter_group_name"
GROUP_COLLECTION_SYNC_PROP = "splatter_group_in_sync"
CLASSIFICATION_ROOT_COLLECTION_NAME = "Pivot"
CLASSIFICATION_COLLECTION_PROP = "splatter_surface_type"

if TYPE_CHECKING:  # pragma: no cover - Blender types only exist at runtime.
    from bpy.types import Collection, Object


class EngineCommunicator:
    """Handles communication with the C++ engine."""

    def __init__(self) -> None:
        self._communicator: Optional[Any] = None

    def get_communicator(self) -> Optional[Any]:
        """Lazy-initialize and cache the engine communicator."""
        if self._communicator is None:
            try:
                from .engine import get_engine_communicator
                self._communicator = get_engine_communicator()
            except RuntimeError:
                self._communicator = None
        return self._communicator

    def send_group_classifications(self, group_surface_map: Dict[str, Any]) -> bool:
        """Send a batch classification update to the engine."""
        if not group_surface_map:
            return True

        communicator = self.get_communicator()
        if not communicator:
            return False

        payload = []
        for name, value in group_surface_map.items():
            try:
                surface_int = int(value)
            except (TypeError, ValueError):
                continue
            payload.append({"group_name": name, "surface_type": surface_int})

        if not payload:
            return True

        try:
            command = {
                "id": COMMAND_SET_GROUP_CLASSIFICATIONS,
                "op": "set_group_classifications",
                "classifications": payload
            }
            response = communicator.send_command(command)
            if not response.get("ok", False):
                error = response.get("error", "Unknown error")
                print(f"Failed to update group classifications: {error}")
                return False
            return True
        except Exception as exc:
            print(f"Error sending group classifications: {exc}")
            return False


class PropertyManager:
    """Centralized manager for object properties that handles engine synchronization."""

    def __init__(self) -> None:
        self._engine_comm = EngineCommunicator()

    # --- Group and Object Queries -------------------------------------------

    def get_group_name(self, obj: Any) -> Optional[str]:
        """Get the group name for an object from its collections."""
        for coll in getattr(obj, "users_collection", []) or []:
            if group := coll.get(GROUP_COLLECTION_PROP):
                return group
        return None

    def iter_group_collections(self) -> Iterator[Any]:
        """Yield all collections tagged as group collections."""
        for coll in bpy.data.collections:
            if coll.get(GROUP_COLLECTION_PROP):
                yield coll

    def iter_unsynced_group_collections(self) -> Iterator[Any]:
        """Yield group collections that are out of sync."""
        for coll in self.iter_group_collections():
            if not coll.get(GROUP_COLLECTION_SYNC_PROP, True):
                yield coll

    def get_managed_group_names(self) -> list[str]:
        """Return sorted list of all managed group names."""
        names = {coll.get(GROUP_COLLECTION_PROP) for coll in self.iter_group_collections()}
        return sorted(name for name in names if name)

    def has_existing_groups(self) -> bool:
        """Check if any groups exist."""
        return any(self.iter_group_collections())

    def get_group_membership_snapshot(self) -> Dict[str, Set[str]]:
        """Return current group memberships from Blender collections."""
        snapshot = {}
        for coll in self.iter_group_collections():
            if group_name := coll.get(GROUP_COLLECTION_PROP):
                objects = getattr(coll, "objects", None) or []
                snapshot[group_name] = {obj.name for obj in objects}
        return snapshot

    # --- Collection Management ---------------------------------------------

    def _get_or_create_root_collection(self, name: str) -> Optional[Any]:
        """Get or create a root collection linked to the scene."""
        scene = getattr(bpy.context, "scene", None)
        if not scene:
            return None

        root = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if scene.collection.children.find(root.name) == -1:
            scene.collection.children.link(root)
        return root

    def _ensure_collection_link(self, parent: Any, child: Any) -> None:
        """Ensure child is linked to parent."""
        if parent and child and parent.children.find(child.name) == -1:
            parent.children.link(child)

    def _tag_group_collection(self, coll: Any, group_name: str) -> None:
        """Tag a collection with group metadata."""
        coll[GROUP_COLLECTION_PROP] = group_name
        if GROUP_COLLECTION_SYNC_PROP not in coll:
            coll[GROUP_COLLECTION_SYNC_PROP] = True

    def _clear_group_collection_metadata(self, coll: Any) -> None:
        """Remove all Pivot metadata from a collection."""
        for key in (GROUP_COLLECTION_PROP, GROUP_COLLECTION_SYNC_PROP, CLASSIFICATION_COLLECTION_PROP):
            coll.pop(key, None)
        coll.color_tag = 'COLOR_NONE'

    def _get_or_create_group_collection(self, obj: Any, group_name: str, root_collection: Optional[Any]) -> Optional[Any]:
        """Get or create a collection for the group."""
        if not root_collection:
            return None

        # Check for existing tagged child
        for coll in root_collection.children:
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                self._tag_group_collection(coll, group_name)
                return coll

        # Handle collection-based groups
        if group_name.endswith("_C"):
            top_coll = self._find_top_collection_for_object(obj, root_collection)
            if not top_coll:
                top_coll = bpy.data.collections.new(group_name)
                root_collection.children.link(top_coll)
            else:
                top_coll.name = group_name
            self._tag_group_collection(top_coll, group_name)
            return top_coll

        # Create new collection
        coll = bpy.data.collections.new(group_name)
        self._tag_group_collection(coll, group_name)
        root_collection.children.link(coll)
        return coll

    def _find_top_collection_for_object(self, obj: Any, root_collection: Any) -> Optional[Any]:
        """Find the top-level collection containing the object."""
        for child in root_collection.children:
            if self._collection_contains_object(child, obj):
                return child
        return None

    def _collection_contains_object(self, coll: Any, obj: Any) -> bool:
        """Check if collection contains object, recursively."""
        try:
            if coll.objects.find(obj.name) != -1:
                return True
        except (AttributeError, ReferenceError):
            return False

        for child in coll.children:
            if self._collection_contains_object(child, obj):
                return True
        return False

    def set_group_name(self, obj: Any, group_name: str, root_collection: Optional[Any] = None) -> bool:
        """Assign an object to a group collection."""
        coll = self._get_or_create_group_collection(obj, group_name, root_collection)
        if not coll:
            return False

        if coll not in obj.users_collection:
            coll.objects.link(obj)

        if root_collection and root_collection is not coll:
            try:
                root_collection.objects.unlink(obj)
            except RuntimeError:
                pass

        self._unlink_other_group_collections(obj, coll)
        return True

    def _unlink_other_group_collections(self, obj: Any, keep: Optional[Any]) -> None:
        """Unlink object from other group collections."""
        for coll in list(getattr(obj, "users_collection", []) or []):
            if coll.get(GROUP_COLLECTION_PROP) and coll is not keep:
                try:
                    coll.objects.unlink(obj)
                except RuntimeError:
                    pass

    # --- Surface Classification --------------------------------------------

    def _get_or_create_surface_collection(self, pivot_root: Any, surface_key: str) -> Optional[Any]:
        """Get or create a surface classification collection."""
        if not pivot_root:
            return None

        for coll in pivot_root.children:
            if coll.get(CLASSIFICATION_COLLECTION_PROP) == surface_key:
                return coll

        # Try to reuse existing collection
        if existing := bpy.data.collections.get(surface_key):
            self._ensure_collection_link(pivot_root, existing)
            existing[CLASSIFICATION_COLLECTION_PROP] = surface_key
            return existing

        # Create new
        surface_coll = bpy.data.collections.new(surface_key)
        surface_coll[CLASSIFICATION_COLLECTION_PROP] = surface_key
        pivot_root.children.link(surface_coll)
        return surface_coll

    def collect_group_classifications(self) -> Dict[str, int]:
        """Collect group -> surface type mappings."""
        result = {}
        pivot_root = bpy.data.collections.get(CLASSIFICATION_ROOT_COLLECTION_NAME)
        if not pivot_root:
            return result

        for surface_coll in pivot_root.children:
            if surface_value := surface_coll.get(CLASSIFICATION_COLLECTION_PROP):
                try:
                    surface_int = int(surface_value)
                except (TypeError, ValueError):
                    continue

                for group_coll in surface_coll.children:
                    if group_name := group_coll.get(GROUP_COLLECTION_PROP):
                        result[group_name] = surface_int

        return result

    def sync_group_classifications(self, group_surface_map: Dict[str, Any]) -> bool:
        """Sync classifications with the engine."""
        return self._engine_comm.send_group_classifications(group_surface_map)

    # --- Sync Management ---------------------------------------------------

    def mark_group_unsynced(self, group_name: str) -> None:
        """Mark a group as needing engine sync."""
        if not group_name:
            return

        engine_state.flag_group_unsynced(group_name)
        for coll in self.iter_group_collections():
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                coll[GROUP_COLLECTION_SYNC_PROP] = False
                coll.color_tag = 'COLOR_03'

    def mark_group_synced(self, group_name: str) -> None:
        """Mark a group as synced with the engine."""
        if not group_name:
            return

        for coll in self.iter_group_collections():
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                coll[GROUP_COLLECTION_SYNC_PROP] = True
                coll.color_tag = 'COLOR_04'

        engine_state.clear_group_unsynced(group_name)

    def cleanup_empty_group_collections(self) -> list[str]:
        """Remove metadata from empty group collections."""
        cleared = []
        for coll in list(self.iter_group_collections()):
            if not getattr(coll, "objects", []):
                if group_name := coll.get(GROUP_COLLECTION_PROP):
                    cleared.append(group_name)
                self._clear_group_collection_metadata(coll)
        return cleared

    # --- Convenience Methods ----------------------------------------------

    def get_group_collections(self) -> list[Any]:
        """Return all group collections as a list."""
        return list(self.iter_group_collections())

    def get_unsynced_group_collections(self) -> list[Any]:
        """Return unsynced group collections as a list."""
        return list(self.iter_unsynced_group_collections())


# Global instance
_property_manager = PropertyManager()

def get_property_manager() -> PropertyManager:
    """Get the global property manager instance."""
    return _property_manager
