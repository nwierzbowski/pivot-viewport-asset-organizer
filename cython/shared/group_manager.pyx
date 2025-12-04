"""Group management for Blender collections with integrated sync state.

Responsibilities:
- Manage group collections and their metadata
- Track sync status of groups with the C++ engine
- Handle group membership operations
- Provide group-related queries and utilities
- Track name changes for managed groups
"""

import bpy
from typing import Any, Dict, Iterator, Optional, Set

cdef class GroupManager:
    """Manages group collections and their metadata with integrated sync state."""

    cdef dict _sync_state
    cdef dict _last_origin_base_state
    cdef dict _name_tracker
    cdef object _subscription_owner

    def __init__(self) -> None:
        self._sync_state = {}
        self._last_origin_base_state = {}
        self._name_tracker = {}
        self._subscription_owner = object()  # Owner object for msgbus subscriptions

    def reset_state(self) -> None:
        """Reset all state to initial values, as if the GroupManager was just created.
        
        This is called when loading a new file to ensure clean state.
        Note: Keeps the same subscription_owner to avoid memory leaks from orphaned subscriptions.
        """
        try:
            data = getattr(bpy, "data", None)
            if data:
                collections = getattr(data, "collections", None)
                if collections:
                    for name in set(self._name_tracker.values()):
                        coll = collections.get(name)
                        if coll and coll.color_tag in {'COLOR_03', 'COLOR_04'}:
                            coll.color_tag = 'NONE'
        except Exception:
            pass
        
        self._sync_state.clear()
        self._name_tracker.clear()
        self._last_origin_base_state.clear()
        # Keep the same subscription_owner to avoid memory leaks from orphaned msgbus subscriptions

    # ==================== Blender API ====================

    def get_objects_collection(self) -> Optional[Any]:
        """Get the objects collection from the scene's pivot properties."""
        objects_collection = bpy.context.scene.pivot.objects_collection
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
            synced = self._sync_state.get(coll.name)

            # 1. Determine the color that it *should* be.
            correct_color = 'COLOR_04' if synced else 'COLOR_03'
            
            # 2. Check if the collection's current color is already correct.
            if coll.color_tag != correct_color:
                # 3. Only perform the expensive write operation if it's wrong.
                coll.color_tag = correct_color

    def update_orphaned_groups(self) -> None:
        """Detect and immediately handle orphaned groups.
        
        Returns a list of orphaned group names that should be deleted from the engine.
        Orphaned groups are: collections that were deleted or moved outside Objects.
        """
        orphaned = []
        objects_collection = self.get_objects_collection()
        
        for coll_name in list(self._sync_state.keys()):
            if coll_name not in bpy.data.collections:
                orphaned.append(coll_name)
                continue
            coll = bpy.data.collections[coll_name]
            if coll_name not in objects_collection.children or not self._has_mesh_objects(coll):
                orphaned.append(coll_name)
        
        return orphaned

    # ==================== Name Change Tracking ====================

    def _subscribe_to_group(self, collection: Any) -> None:
        """Subscribe to name changes for a collection."""
        try:
            if not collection:
                print(f"[Pivot] Collection is None")
                return
            
            if not hasattr(collection, 'name'):
                print(f"[Pivot] Collection has no name attribute")
                return
                
            collection_name = collection.name
            subscribe_to = collection.path_resolve("name", False)
            
            from pivot.handlers import on_group_name_changed
            
            bpy.msgbus.subscribe_rna(
                key=subscribe_to,
                owner=self._subscription_owner,
                args=(collection, self),
                notify=on_group_name_changed,
            )
            
            self._name_tracker[collection] = collection_name
            # print(f"[Pivot] Successfully subscribed to '{collection_name}'")
            
        except Exception as e:
            print(f"[Pivot] Failed to subscribe to name changes: {e}")
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
                self._last_origin_base_state.setdefault(name, True)
                
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
        print("Dropping groups:")
        print(group_names)
        for name in group_names:
            if name in self._sync_state:
                del self._sync_state[name]
                if name in self._last_origin_base_state:
                    del self._last_origin_base_state[name]
                # Unsubscribe when group is dropped
                self._unsubscribe_group(name)
        print("Remaining state",self._sync_state)

    cpdef bint is_managed_collection(self, str collection_name):
        """Check if the given collection name is managed."""
        return collection_name in self._sync_state

    # ==================== Sync State ====================

    cpdef void set_group_unsynced(self, str group_name):
        """Mark a group as unsynced (only if it already exists in sync state)."""
        if group_name and group_name in self._sync_state:
            self._sync_state[group_name] = False

    cpdef void set_groups_synced(self, list group_names):
        """Mark groups as synced (only if they already exist in sync state)."""
        cdef str name
        for name in group_names:
            if name and name in self._sync_state:
                self._sync_state[name] = True

    cpdef void set_groups_last_origin_method_base(self, list group_names, bint used_base):
        """Record whether each managed group was last transformed with the BASE origin method."""
        cdef str name
        for name in group_names:
            if name:
                self._last_origin_base_state[name] = bool(used_base)

    cpdef dict get_last_origin_method_state(self):
        """Return a copy of the last origin method state mapping."""
        return dict(self._last_origin_base_state)

    cpdef bint was_group_last_transformed_using_base(self, str group_name):
        """Return True if the group was last transformed using the BASE origin method."""
        if not group_name:
            return False
        return bool(self._last_origin_base_state.get(group_name, True))

    cpdef bint was_object_last_transformed_using_base(self, object obj):
        """Return True if the group owning the object was last transformed using BASE."""
        group_name = self.get_group_name(obj)
        if not group_name:
            return True
        return self.was_group_last_transformed_using_base(group_name)

    cpdef dict get_sync_state(self):
        """Return a copy of the full sync state dict (group_name -> synced bool)."""
        return dict(self._sync_state)

    cpdef dict get_name_tracker(self):
        """Get the name tracker dictionary."""
        return self._name_tracker

    cpdef dict get_sync_state_dict(self):
        """Get the sync state dictionary."""
        return self._sync_state

    cpdef get_sync_state_keys(self):
        """Get the keys of the sync state dict (managed group names)."""
        return set(self._sync_state.keys())


# Global instance
cdef GroupManager _group_manager = GroupManager()

cpdef GroupManager get_group_manager():
    """Get the global group manager instance."""
    return _group_manager
