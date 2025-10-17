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
        """Mark a group as unsynced and update its visual representation."""
        if not group_name:
            return
        
        self._sync_state[group_name] = False
        
    cpdef dict get_sync_state(self):
        """Return a copy of the full sync state dict (group_name -> synced bool)."""
        return self._sync_state.copy()

    cpdef void set_groups_synced(self, list full_groups, list group_names):
        """Create group collections, set colors, and mark as synced."""
        
        # Create group collections and set colors
        get_group_manager().ensure_group_collections(full_groups, group_names)
        
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