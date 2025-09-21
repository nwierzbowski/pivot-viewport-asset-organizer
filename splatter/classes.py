# type: ignore
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, EnumProperty

# Import C enum values from Cython module
from . import classification

class ObjectAttributes(PropertyGroup):
    isSeating: BoolProperty(name="Is Seating")
    isSurface: BoolProperty(name="Is Surface")
    surfaceType: EnumProperty(
        name="Surface Type",
        description="Type of surface",
        items=classification.SURFACE_TYPE_ITEMS,
        default=classification.SURFACE_WALL,
    )
