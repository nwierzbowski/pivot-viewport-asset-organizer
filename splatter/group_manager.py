"""Group management for Blender collections.

Responsibilities:
- Manage group collections and their metadata
- Handle group membership operations
- Provide group-related queries and utilities
"""

import bpy
from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional, Set

from .collection_manager import get_collection_manager

# Property keys for collection metadata
GROUP_COLLECTION_PROP = "splatter_group_name"
GROUP_COLLECTION_SYNC_PROP = "splatter_group_in_sync"

if TYPE_CHECKING:  # pragma: no cover - Blender types only exist at runtime.
    from bpy.types import Collection, Object


class GroupManager:
    """Manages group collections and their metadata."""

    def __init__(self) -> None:
        self._collection_manager = get_collection_manager()

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

    def iter_group_objects(self, group_name: str) -> Iterator[Any]:
        """Iterate over objects in collections tagged with the given group name."""
        for coll in self.iter_group_collections():
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                # Return objects from the first matching collection (groups assumed unique)
                return iter(coll.objects)
        return iter([])

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
            top_coll = self._collection_manager.find_top_collection_for_object(obj, root_collection)
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

    def _tag_group_collection(self, coll: Any, group_name: str) -> None:
        """Tag a collection with group metadata."""
        coll[GROUP_COLLECTION_PROP] = group_name
        if GROUP_COLLECTION_SYNC_PROP not in coll:
            coll[GROUP_COLLECTION_SYNC_PROP] = True

    def _clear_group_collection_metadata(self, coll: Any) -> None:
        """Remove all group metadata from a collection."""
        for key in (GROUP_COLLECTION_PROP, GROUP_COLLECTION_SYNC_PROP):
            coll.pop(key, None)
        coll.color_tag = 'COLOR_NONE'

    def _unlink_other_group_collections(self, obj: Any, keep: Optional[Any]) -> None:
        """Unlink object from other group collections."""
        for coll in list(getattr(obj, "users_collection", []) or []):
            if coll.get(GROUP_COLLECTION_PROP) and coll is not keep:
                try:
                    coll.objects.unlink(obj)
                except RuntimeError:
                    pass

    def _get_group_collection_for_object(self, obj: Any, group_name: Optional[str]) -> Optional[Any]:
        """Find the group collection for an object."""
        if not group_name:
            return None
        for coll in getattr(obj, "users_collection", []) or []:
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                return coll
        return None

    def _ensure_group_collection(self, obj: Any, group_name: Optional[str], fallback_name: str) -> Optional[Any]:
        """Ensure the object has a group collection."""
        group_collection = self._get_group_collection_for_object(obj, group_name)
        if group_collection is not None:
            return group_collection

        group_collection = bpy.data.collections.get(fallback_name)
        if group_collection is None:
            group_collection = bpy.data.collections.new(fallback_name)
        if group_collection not in obj.users_collection:
            group_collection.objects.link(obj)
        self._tag_group_collection(group_collection, group_name or fallback_name)
        return group_collection

    # --- Convenience Methods ----------------------------------------------

    def get_group_collections(self) -> list[Any]:
        """Return all group collections as a list."""
        return list(self.iter_group_collections())

    def get_unsynced_group_collections(self) -> list[Any]:
        """Return unsynced group collections as a list."""
        return list(self.iter_unsynced_group_collections())


# Global instance
_group_manager = GroupManager()

def get_group_manager() -> GroupManager:
    """Get the global group manager instance."""
    return _group_manager