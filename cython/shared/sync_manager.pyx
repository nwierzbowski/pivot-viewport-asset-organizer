"""Synchronization state management for engine operations.

Responsibilities:
- Track sync status of groups with the C++ engine
- Manage sync state in memory (avoids Blender undo conflicts)
"""

from typing import Dict

from splatter.group_manager import get_group_manager


cdef class SyncManager:
    """Manages synchronization state between Blender and the C++ engine.
    
    Tracks which groups need syncing using in-memory state only.
    This keeps sync state separate from Blender's undo system.
    """

    cdef dict _sync_state

    def __init__(self) -> None:
        # Maps group_name -> bool (True = synced, False = unsynced)
        self._sync_state = {}

    cpdef void set_group_unsynced(self, str group_name):
        """Remember that a group needs a round-trip to the engine."""
        if group_name:
            self._sync_state[group_name] = False
        
    cpdef set get_unsynced_groups(self):
        """Return a set of group names that are out of sync."""
        return {name for name, synced in self._sync_state.items() if not synced}

    cpdef void set_groups_synced(self, list full_groups, list group_names, object parent_collection):
        """Create group collections, set colors, and mark as synced."""
        group_manager = get_group_manager()
        
        # Create group collections
        group_manager.create_or_get_group_collections(full_groups, group_names, parent_collection)
        
        # Set colors for all created groups
        group_manager.set_group_colors(group_names)
        
        # Mark groups as synced after successful creation
        cdef str name
        for name in group_names:
            if name:
                self._sync_state[name] = True


# Global instance
cdef SyncManager _sync_manager = SyncManager()

cpdef SyncManager get_sync_manager():
    """Get the global sync manager instance."""
    return _sync_manager