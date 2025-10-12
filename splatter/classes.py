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


class SceneAttributes(PropertyGroup):
    objects_collection: PointerProperty(
        name=LABEL_OBJECTS_COLLECTION.rstrip(":"),
        description="Collection containing objects to scatter",
        type=Collection,
    )
    room_collection: PointerProperty(
        name=LABEL_ROOM_COLLECTION.rstrip(":"),
        description="Collection containing room geometry",
        type=Collection,
    )
    license_type: StringProperty(
        name=LABEL_LICENSE_TYPE.rstrip(":"),
        description="License type (read-only, determined by engine)",
        default="UNKNOWN",
    )


class ObjectAttributes(PropertyGroup):
    # isSeating: BoolProperty(name="Is Seating")
    # isSurface: BoolProperty(name="Is Surface")
    pass
