"""Group management for Blender collections with integrated sync state.

Responsibilities:
- Manage group collections and their metadata
- Track sync status of groups with the C++ engine
- Handle group membership operations
- Provide group-related queries and utilities
- Track name changes for managed groups
"""

import bpy
from typing import Any, Callable, Dict, Iterator, Optional, Set

cdef class GroupManager:
    """Manages group collections and their metadata with integrated sync state."""

    cdef dict _sync_state
    cdef set _orphaned_groups
    cdef dict _name_tracker
    cdef object _subscription_owner

    def __init__(self) -> None:
        self._sync_state = {}
        self._orphaned_groups = set()
        self._name_tracker = {}
        self._subscription_owner = object()  # Owner object for msgbus subscriptions

    # ==================== Blender API ====================

    def get_objects_collection(self) -> Optional[Any]:
        """Get the objects collection from the scene's splatter properties."""
        objects_collection = bpy.context.scene.splatter.objects_collection
        return objects_collection if objects_collection else bpy.context.scene.collection

    cpdef str get_group_name(self, obj):
        """Get the group name for an object from its collections."""
        collections = getattr(obj, "users_collection", None)
        if not collections:
            return None
        
        cdef object coll
        for coll in collections:
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

    # ==================== Name Change Tracking ====================

    def _subscribe_to_group(self, collection: Any) -> None:
        """Subscribe to name changes for a collection."""
        try:
            if not collection:
                print(f"[Splatter] Collection is None")
                return
            
            if not hasattr(collection, 'name'):
                print(f"[Splatter] Collection has no name attribute")
                return
                
            collection_name = collection.name
            subscribe_to = collection.path_resolve("name", False)
            
            from splatter.handlers import on_group_name_changed
            
            bpy.msgbus.subscribe_rna(
                key=subscribe_to,
                owner=self._subscription_owner,
                args=(collection, self),
                notify=on_group_name_changed,
            )
            
            self._name_tracker[collection] = collection_name
            print(f"[Splatter] Successfully subscribed to '{collection_name}'")
            
        except Exception as e:
            print(f"[Splatter] Failed to subscribe to name changes: {e}")
            import traceback
            traceback.print_exc()

    def _unsubscribe_group(self, group_name: str) -> None:
        """Unsubscribe from name changes for a specific group name."""
        # Find and remove the collection from tracker by name
        collections_to_remove = []
        for collection, tracked_name in list(self._name_tracker.items()):
            if tracked_name == group_name:
                collections_to_remove.append(collection)
        
        for collection in collections_to_remove:
            del self._name_tracker[collection]

    # ==================== Managed Groups ====================

    cpdef void update_managed_group_names(self, list group_names):
        """Update the set of managed collection names by merging with existing names.
        
        When new groups are added, subscribe to their name changes.
        """
        cdef str name
        for name in group_names:
            if name and name not in self._sync_state:
                self._sync_state[name] = True
                
                # Subscribe to name changes when group is added
                if name in bpy.data.collections:
                    collection = bpy.data.collections[name]
                    self._subscribe_to_group(collection)

    cpdef set get_managed_group_names_set(self):
        """Return the set of all managed collection names."""
        return set(self._sync_state.keys())

    cpdef bint has_existing_groups(self):
        """Check if any groups exist."""
        return bool(self._sync_state)

    cpdef void drop_groups(self, list group_names):
        """Drop multiple groups from being managed and unsubscribe from name changes."""
        cdef str name
        for name in group_names:
            if name in self._sync_state:
                del self._sync_state[name]
                # Unsubscribe when group is dropped
                self._unsubscribe_group(name)

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

    cpdef set get_orphaned_groups(self):
        """Get the current set of orphaned groups."""
        return self._orphaned_groups

    cpdef void clear_orphaned_groups(self):
        """Clean up orphaned groups locally: remove from managed set and clear orphans.

        This should be called after dropping from the engine to keep state consistent.
        """
        cdef list orphans = list(self._orphaned_groups)
        if not orphans:
            return

        cdef int count = len(orphans)
        self.drop_groups(orphans)
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

    cpdef dict get_name_tracker(self):
        """Get the name tracker dictionary."""
        return self._name_tracker

    cpdef dict get_sync_state_dict(self):
        """Get the sync state dictionary."""
        return self._sync_state

    cpdef set get_orphaned_groups_set(self):
        """Get the orphaned groups set."""
        return self._orphaned_groups

    cpdef get_sync_state_keys(self):
        """Get the keys of the sync state dict (managed group names)."""
        return set(self._sync_state.keys())


# Global instance
cdef GroupManager _group_manager = GroupManager()

cpdef GroupManager get_group_manager():
    """Get the global group manager instance."""
    return _group_manager
