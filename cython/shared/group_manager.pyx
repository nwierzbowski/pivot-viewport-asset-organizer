"""Group management for Blender collections with integrated sync state.

Responsibilities:
- Manage group collections and their metadata
- Track sync status of groups with the C++ engine
- Handle group membership operations
- Provide group-related queries and utilities
"""

import bpy
from typing import Any, Dict, Iterator, Optional, Set

cdef class GroupManager:
    """Manages group collections and their metadata with integrated sync state."""

    cdef dict _sync_state
    cdef set _orphaned_groups

    def __init__(self) -> None:
        self._sync_state = {}
        self._orphaned_groups = set()

    # ==================== Blender API ====================

    def get_objects_collection(self) -> Optional[Any]:
        """Get the objects collection from the scene's splatter properties."""
        objects_collection = bpy.context.scene.splatter.objects_collection
        return objects_collection if objects_collection else bpy.context.scene.collection

    def get_group_name(self, obj: Any) -> Optional[str]:
        """Get the group name for an object from its collections."""
        for coll in getattr(obj, "users_collection", []) or []:
            if coll.name in self._sync_state:
                return coll.name
        return None

    def iter_group_collections(self) -> Iterator[Any]:
        """Yield all collections that are in the managed collections set."""
        for coll_name in self._sync_state:
            if coll_name in bpy.data.collections:
                yield bpy.data.collections[coll_name]

    def get_group_membership_snapshot(self) -> Dict[str, Set[str]]:
        """Return current group memberships from Blender collections."""
        snapshot = {}
        for coll in self.iter_group_collections():
            objects = getattr(coll, "objects", None) or []
            snapshot[coll.name] = {obj.name for obj in objects}
        return snapshot

    def _has_mesh_objects(self, coll: Any) -> bool:
        """Check if the collection or its children contain any mesh objects."""
        for obj in coll.objects:
            if obj.type == 'MESH':
                return True
        for child in coll.children:
            if self._has_mesh_objects(child):
                return True
        return False

    def update_colors(self) -> None:
        """Update color tags for collections based on sync state."""
        for coll in self.iter_group_collections():
            if self._is_orphaned_internal(coll.name):
                coll.color_tag = "NONE"
                continue
            synced = self._sync_state.get(coll.name)

            # 1. Determine the color that it *should* be.
            correct_color = 'COLOR_04' if synced else 'COLOR_03'
            
            # 2. Check if the collection's current color is already correct.
            if coll.color_tag != correct_color:
                # 3. Only perform the expensive write operation if it's wrong.
                coll.color_tag = correct_color

    def update_orphaned_groups(self) -> None:
        """Update the set of orphaned groups by accumulating new orphans."""
        objects_collection = self.get_objects_collection()
        
        for coll_name in list(self._sync_state.keys()):
            if coll_name in self._orphaned_groups:
                continue  # Already marked as orphaned
            if coll_name not in bpy.data.collections:
                self._orphaned_groups.add(coll_name)
                continue
            coll = bpy.data.collections[coll_name]
            if coll_name not in objects_collection.children or not self._has_mesh_objects(coll):
                self._orphaned_groups.add(coll_name)

    # ==================== Managed Groups ====================

    cpdef void update_managed_group_names(self, list group_names):
        """Update the set of managed collection names by merging with existing names."""
        cdef str name
        for name in group_names:
            if name and name not in self._sync_state:
                self._sync_state[name] = True

    cpdef set get_managed_group_names_set(self):
        """Return the set of all managed collection names."""
        return set(self._sync_state.keys())

    cpdef bint has_existing_groups(self):
        """Check if any groups exist."""
        return bool(self._sync_state)

    cpdef void drop_groups(self, list group_names):
        """Drop multiple groups from being managed: remove from managed set."""
        cdef str name
        for name in group_names:
            if name in self._sync_state:
                del self._sync_state[name]

    cpdef bint is_managed_collection(self, str collection_name):
        """Check if the given collection name is managed."""
        return collection_name in self._sync_state

    # ==================== Sync State ====================

    cpdef void set_group_unsynced(self, str group_name):
        """Mark a group as unsynced."""
        if group_name:
            self._sync_state[group_name] = False

    cpdef void set_groups_synced(self, list group_names):
        """Mark groups as synced."""
        cdef str name
        for name in group_names:
            if name:
                self._sync_state[name] = True

    cpdef dict get_sync_state(self):
        """Return a copy of the full sync state dict (group_name -> synced bool)."""
        return dict(self._sync_state)

    # ==================== Orphaned Groups ====================

    cpdef list get_orphaned_groups(self):
        """Get the current list of orphaned groups."""
        return list(self._orphaned_groups)

    cpdef void clear_orphaned_groups(self):
        """Clear the orphaned set after processing all orphaned groups."""
        self._orphaned_groups.clear()

    cpdef void add_orphaned_group(self, str group_name):
        """Add a group to the orphaned set."""
        if group_name:
            self._orphaned_groups.add(group_name)

    cpdef bint is_orphaned(self, str group_name):
        """Check if a group is orphaned."""
        return group_name in self._orphaned_groups

    cdef bint _is_orphaned_internal(self, str group_name):
        """Internal fast check if a group is orphaned (for Cython code)."""
        return group_name in self._orphaned_groups

    # ==================== Cleanup ====================

    cpdef void cleanup_orphaned_groups_locally(self):
        """Clean up orphaned groups locally: remove from managed set and clear orphans.

        This should be called after dropping from the engine to keep state consistent.
        """
        cdef list orphans = list(self._orphaned_groups)
        if not orphans:
            return

        # Remove from managed set locally
        self.drop_groups(orphans)
        
        # Clear the orphaned groups set
        self.clear_orphaned_groups()

        print(f"[Splatter] Cleaned up {len(orphans)} orphaned groups locally")


# Global instance
cdef GroupManager _group_manager = GroupManager()

cpdef GroupManager get_group_manager():
    """Get the global group manager instance."""
    return _group_manager
