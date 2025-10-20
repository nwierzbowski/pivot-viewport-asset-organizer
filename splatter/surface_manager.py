"""Surface classification management for Blender collections.

Responsibilities:
- Manage surface classification collections
- Handle surface type assignments and hierarchy
"""

import bpy
from typing import Any, Dict, Optional

from .collection_manager import get_collection_manager
from .lib import group_manager
from .lib import classification

# Property keys for collection metadata
CLASSIFICATION_ROOT_COLLECTION_NAME = "Pivot Classifications"
CLASSIFICATION_ROOT_MARKER_PROP = "splatter_is_classification_root"
CLASSIFICATION_COLLECTION_PROP = "splatter_surface_type"
CLASSIFICATION_MARKER_PROP = "splatter_is_classification_collection"


class SurfaceManager:
    """Manages surface classification collections and hierarchy."""

    def __init__(self) -> None:
        self._collection_manager = get_collection_manager()
        self._group_manager = group_manager.get_group_manager()
        # Build a mapping from surface key to display name

    def _get_surface_display_name(self, surface_key: str) -> str:
        """Get the display name for a surface key."""
        return classification.SURFACE_TYPE_NAMES.get(surface_key, surface_key)

    def _find_or_create_root_collection(self) -> Optional[Any]:
        """Find the root classification collection by marker, or create it if needed."""
        # First try to find existing root by marker property
        for coll in bpy.data.collections:
            if coll.get(CLASSIFICATION_ROOT_MARKER_PROP, False):
                return coll
        
        # If not found, create or get by name and mark it
        return self._collection_manager.get_or_create_root_collection(CLASSIFICATION_ROOT_COLLECTION_NAME)

    def get_or_create_surface_collection(self, pivot_root: Any, surface_key: str) -> Optional[Any]:
        """Get or create a surface classification collection."""
        if not pivot_root:
            return None

        for coll in pivot_root.children:
            if coll.get(CLASSIFICATION_COLLECTION_PROP) == surface_key:
                return coll

        # Get display name for the collection
        collection_name = self._get_surface_display_name(surface_key)
        
        # Try to reuse existing collection
        if existing := bpy.data.collections.get(collection_name):
            self._collection_manager.ensure_collection_link(pivot_root, existing)
            existing[CLASSIFICATION_COLLECTION_PROP] = surface_key
            existing[CLASSIFICATION_MARKER_PROP] = True
            return existing

        # Create new
        surface_coll = bpy.data.collections.new(collection_name)
        surface_coll[CLASSIFICATION_COLLECTION_PROP] = surface_key
        surface_coll[CLASSIFICATION_MARKER_PROP] = True
        pivot_root.children.link(surface_coll)
        return surface_coll

    def collect_group_classifications(self) -> Dict[str, int]:
        """Collect group -> surface type mappings."""
        result = {}
        pivot_root = self._find_or_create_root_collection()
        if not pivot_root:
            return result

        for surface_coll in pivot_root.children:
            if surface_value := surface_coll.get(CLASSIFICATION_COLLECTION_PROP):
                try:
                    surface_int = int(surface_value)
                except (TypeError, ValueError):
                    continue

                for group_coll in surface_coll.children:
                    if self._group_manager.is_managed_collection(group_coll.name):
                        result[group_coll.name] = surface_int

        return result

    def sync_group_classifications(self, group_surface_map: Dict[str, Any]) -> bool:
        """Sync classifications with the engine."""
        try:
            from .engine import get_engine_communicator
            engine = get_engine_communicator()
            return engine.send_group_classifications(group_surface_map)
        except RuntimeError:
            return False

    def organize_group_into_surface(self, group_collection: Any, surface_key: str) -> None:
        """Organize a single group collection into the surface hierarchy.
        
        Args:
            group_collection: The group collection to organize
            surface_key: The surface type key (str)
        """
        pivot_root = self._find_or_create_root_collection()
        if not pivot_root:
            return
        
        # Mark root as classification root collection
        pivot_root[CLASSIFICATION_ROOT_MARKER_PROP] = True
        
        # Get/create surface collection
        surface_coll = self.get_or_create_surface_collection(pivot_root, surface_key)
        if not surface_coll:
            return
        
        # Unlink from other surface containers FIRST
        for other_coll in pivot_root.children:
            if other_coll is not surface_coll:
                other_children = getattr(other_coll, "children", None)
                if other_children and other_children.find(group_collection.name) != -1:
                    other_children.unlink(group_collection)
        
        # Link group to surface collection (only if not already linked)
        if surface_coll.children.find(group_collection.name) == -1:
            self._collection_manager.ensure_collection_link(surface_coll, group_collection)

    def organize_groups_into_surfaces(self, group_names: list[str], surface_types: list[int]) -> None:
        """Organize multiple group collections into the surface hierarchy using parallel lists."""
        
        for idx, group_name in enumerate(group_names):
            group_coll = bpy.data.collections.get(group_name)
            if not group_coll:
                continue
            
            surface_key = str(surface_types[idx])
            self.organize_group_into_surface(group_coll, surface_key)

    def is_classification_collection(self, collection: Any) -> bool:
        """Check if a collection is a classification collection."""
        if not collection:
            return False
        return collection.get(CLASSIFICATION_MARKER_PROP, False)

    def is_classification_root_collection(self, collection: Any) -> bool:
        """Check if a collection is the classification root collection."""
        if not collection:
            return False
        return collection.get(CLASSIFICATION_ROOT_MARKER_PROP, False)


# Global instance
_surface_manager = SurfaceManager()

def get_surface_manager() -> SurfaceManager:
    """Get the global surface manager instance."""
    return _surface_manager