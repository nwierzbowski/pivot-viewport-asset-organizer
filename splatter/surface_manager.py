"""Surface classification management for Blender collections.

Responsibilities:
- Manage surface classification collections
- Handle surface type assignments
- Collect and sync surface classifications with the engine
"""

import bpy
from typing import TYPE_CHECKING, Any, Dict, Optional

from .collection_manager import get_collection_manager
from .group_manager import get_group_manager, GROUP_COLLECTION_PROP, GROUP_COLLECTION_SYNC_PROP

# Property keys for collection metadata
CLASSIFICATION_ROOT_COLLECTION_NAME = "Pivot"
CLASSIFICATION_COLLECTION_PROP = "splatter_surface_type"

if TYPE_CHECKING:  # pragma: no cover - Blender types only exist at runtime.
    from bpy.types import Collection, Object


class SurfaceManager:
    """Manages surface classification collections and operations."""

    def __init__(self) -> None:
        self._collection_manager = get_collection_manager()
        self._group_manager = get_group_manager()

    def get_or_create_surface_collection(self, pivot_root: Any, surface_key: str) -> Optional[Any]:
        """Get or create a surface classification collection."""
        if not pivot_root:
            return None

        for coll in pivot_root.children:
            if coll.get(CLASSIFICATION_COLLECTION_PROP) == surface_key:
                return coll

        # Try to reuse existing collection
        if existing := bpy.data.collections.get(surface_key):
            self._collection_manager.ensure_collection_link(pivot_root, existing)
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
        try:
            from .engine import get_engine_communicator
            engine = get_engine_communicator()
            return engine.send_group_classifications(group_surface_map)
        except RuntimeError:
            return False

    def assign_surface_collection(self, obj: Any, surface_value: Any) -> None:
        """Assign an object to a surface classification collection."""
        surface_key = str(surface_value)
        pivot_root = self._collection_manager.get_or_create_root_collection(CLASSIFICATION_ROOT_COLLECTION_NAME)
        if not pivot_root:
            return

        group_name = self._group_manager.get_group_name(obj)
        group_collection = self._group_manager._ensure_group_collection(obj, group_name, group_name or surface_key)

        surface_collection = self.get_or_create_surface_collection(pivot_root, surface_key)
        if not surface_collection:
            return

        self._collection_manager.ensure_collection_link(surface_collection, group_collection)
        group_collection[CLASSIFICATION_COLLECTION_PROP] = surface_key

        # Unlink from other surface containers
        for coll in pivot_root.children:
            if coll is surface_collection:
                continue
            children = getattr(coll, "children", None)
            if children and children.find(group_collection.name) != -1:
                children.unlink(group_collection)

    def organize_groups_into_surfaces(self, group_collections: Dict[str, Any], group_surface_map: Dict[str, str]) -> None:
        """Organize group collections into surface type hierarchy.
        
        Args:
            group_collections: Dict mapping group_name -> group_collection object
            group_surface_map: Dict mapping group_name -> surface_key (str)
        """
        pivot_root = self._collection_manager.get_or_create_root_collection(CLASSIFICATION_ROOT_COLLECTION_NAME)
        if not pivot_root:
            return
        
        for group_name, group_coll in group_collections.items():
            if not group_coll:
                continue
            
            surface_key = group_surface_map.get(group_name)
            if not surface_key:
                continue
            
            # Get/create surface collection
            surface_coll = self.get_or_create_surface_collection(pivot_root, surface_key)
            if not surface_coll:
                continue
            
            # Link group to surface collection
            self._collection_manager.ensure_collection_link(surface_coll, group_coll)
            
            # Update metadata
            group_coll[CLASSIFICATION_COLLECTION_PROP] = surface_key
            group_coll[GROUP_COLLECTION_SYNC_PROP] = True
            group_coll.color_tag = 'COLOR_04'
            
            # Unlink from other surface containers
            for other_coll in pivot_root.children:
                if other_coll is not surface_coll:
                    other_children = getattr(other_coll, "children", None)
                    if other_children and other_children.find(group_coll.name) != -1:
                        other_children.unlink(group_coll)


# Global instance
_surface_manager = SurfaceManager()

def get_surface_manager() -> SurfaceManager:
    """Get the global surface manager instance."""
    return _surface_manager