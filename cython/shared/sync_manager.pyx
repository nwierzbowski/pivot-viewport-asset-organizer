"""Synchronization state management for engine operations.

Responsibilities:
- Track sync status of groups with the C++ engine
- Manage sync state in memory (avoids Blender undo conflicts)
"""

from typing import Dict


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

    cpdef void set_group_synced(self, str group_name):
        """Mark a group as synced with the engine."""
        if group_name:
            self._sync_state[group_name] = True
        
    cpdef set get_unsynced_groups(self):
        """Return a set of group names that are out of sync."""
        return {name for name, synced in self._sync_state.items() if not synced}


# Global instance
cdef SyncManager _sync_manager = SyncManager()

cpdef SyncManager get_sync_manager():
    """Get the global sync manager instance."""
    return _sync_manager