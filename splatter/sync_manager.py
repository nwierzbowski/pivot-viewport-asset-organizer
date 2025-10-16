"""Synchronization state management for engine operations.

Responsibilities:
- Track sync status of groups with the C++ engine
- Mark groups as synced or unsynced
- Clean up empty collections
"""

import bpy
from typing import TYPE_CHECKING, Any, List

from . import engine_state
from .group_manager import get_group_manager, GROUP_COLLECTION_PROP, GROUP_COLLECTION_SYNC_PROP

if TYPE_CHECKING:  # pragma: no cover - Blender types only exist at runtime.
    from bpy.types import Collection, Object


class SyncManager:
    """Manages synchronization state between Blender and the C++ engine."""

    def __init__(self) -> None:
        self._group_manager = get_group_manager()

    def mark_group_unsynced(self, group_name: str) -> None:
        """Mark a group as needing engine sync."""
        if not group_name:
            return

        engine_state.flag_group_unsynced(group_name)
        for coll in self._group_manager.iter_group_collections():
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                coll[GROUP_COLLECTION_SYNC_PROP] = False
                coll.color_tag = 'COLOR_03'

    def mark_group_synced(self, group_name: str) -> None:
        """Mark a group as synced with the engine."""
        if not group_name:
            return

        for coll in self._group_manager.iter_group_collections():
            if coll.get(GROUP_COLLECTION_PROP) == group_name:
                coll[GROUP_COLLECTION_SYNC_PROP] = True
                coll.color_tag = 'COLOR_04'

        engine_state.clear_group_unsynced(group_name)

    def cleanup_empty_group_collections(self) -> List[str]:
        """Remove metadata from empty group collections."""
        cleared = []
        for coll in list(self._group_manager.iter_group_collections()):
            if not getattr(coll, "objects", []):
                if group_name := coll.get(GROUP_COLLECTION_PROP):
                    cleared.append(group_name)
                self._clear_group_collection_metadata(coll)
        return cleared

    def _clear_group_collection_metadata(self, coll: Any) -> None:
        """Remove all group metadata from a collection."""
        for key in (GROUP_COLLECTION_PROP, GROUP_COLLECTION_SYNC_PROP):
            coll.pop(key, None)
        coll.color_tag = 'COLOR_NONE'


# Global instance
_sync_manager = SyncManager()

def get_sync_manager() -> SyncManager:
    """Get the global sync manager instance."""
    return _sync_manager