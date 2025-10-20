# type: ignore
from bpy.types import PropertyGroup, Collection
from bpy.props import BoolProperty, EnumProperty, StringProperty, PointerProperty
import bpy

# Import C enum values from Cython module
from .lib import classification
from .constants import LICENSE_STANDARD, LICENSE_PRO

# UI Labels (property names derived from these)
LABEL_OBJECTS_COLLECTION = "Objects:"
LABEL_ROOM_COLLECTION = "Room:"
LABEL_SURFACE_TYPE = "Surface:"
LABEL_LICENSE_TYPE = "License:"

# Marker property to identify classification collections
CLASSIFICATION_MARKER_PROP = "splatter_is_classification_collection"

def _is_descendant_of_classification_collection(coll):
    """Check if a collection is a descendant of any classification collection."""
    def check_parents(current_coll):
        for parent_coll in bpy.data.collections:
            if parent_coll.get(CLASSIFICATION_MARKER_PROP, False):
                if _is_in_subtree(current_coll, parent_coll):
                    return True
        return False
    
    def _is_in_subtree(target_coll, root_coll):
        """Check if target_coll is in the subtree of root_coll."""
        if target_coll == root_coll:
            return True
        for child in root_coll.children:
            if _is_in_subtree(target_coll, child):
                return True
        return False
    
    return check_parents(coll)

def poll_visible_collections(self, coll):
    """
    Only show collections that are NOT marked as classification collections
    and are NOT descendants of classification collections.
    We use .get() to avoid an error if the property doesn't exist.
    """
    # Check if this collection itself is marked
    if coll.get(CLASSIFICATION_MARKER_PROP, False):
        return False
    
    # Check if this collection is a descendant of any classification collection
    if _is_descendant_of_classification_collection(coll):
        return False
    
    return True


class SceneAttributes(PropertyGroup):
    objects_collection: PointerProperty(
        name=LABEL_OBJECTS_COLLECTION.rstrip(":"),
        description="Collection containing objects to scatter",
        type=Collection,
        poll=poll_visible_collections,
    )
    room_collection: PointerProperty(
        name=LABEL_ROOM_COLLECTION.rstrip(":"),
        description="Collection containing room geometry",
        type=Collection,
        poll=poll_visible_collections,
    )
    license_type: StringProperty(
        name=LABEL_LICENSE_TYPE.rstrip(":"),
        description="License type (read-only, determined by engine)",
        default="UNKNOWN",
    )
