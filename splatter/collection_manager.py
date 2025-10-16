"""Low-level Blender collection management utilities.

Responsibilities:
- Create and manage Blender collections
- Handle collection linking and unlinking
- Collection hierarchy operations
"""

import bpy
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - Blender types only exist at runtime.
    from bpy.types import Collection, Object


class CollectionManager:
    """Handles low-level Blender collection operations."""

    def __init__(self) -> None:
        pass

    def get_or_create_root_collection(self, name: str) -> Optional[Any]:
        """Get or create a root collection linked to the scene."""
        scene = getattr(bpy.context, "scene", None)
        if not scene:
            return None

        root = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if scene.collection.children.find(root.name) == -1:
            scene.collection.children.link(root)
        return root

    def ensure_collection_link(self, parent: Any, child: Any) -> None:
        """Ensure child is linked to parent."""
        if parent and child and parent.children.find(child.name) == -1:
            parent.children.link(child)

    def find_top_collection_for_object(self, obj: Any, root_collection: Any) -> Optional[Any]:
        """Find the top-level collection containing the object."""
        for child in root_collection.children:
            if self.collection_contains_object(child, obj):
                return child
        return None

    def collection_contains_object(self, coll: Any, obj: Any) -> bool:
        """Check if collection contains object, recursively."""
        try:
            if coll.objects.find(obj.name) != -1:
                return True
        except (AttributeError, ReferenceError):
            return False

        for child in coll.children:
            if self.collection_contains_object(child, obj):
                return True
        return False


# Global instance
_collection_manager = CollectionManager()

def get_collection_manager() -> CollectionManager:
    """Get the global collection manager instance."""
    return _collection_manager