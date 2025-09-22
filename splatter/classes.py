# type: ignore
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, EnumProperty, StringProperty

# Import C enum values from Cython module
from . import classification

def update_surface_type(self, context):
    """Callback that runs when surfaceType enum is changed"""
    import bpy

    # Only run callback if this object is the active object (user-initiated change)
    if self.id_data != bpy.context.active_object:
        return

    new_surface_type_str = self.surfaceType
    group_name = self.group_name

    print(f"Updating surface type to {new_surface_type_str} for group {group_name}")

    if not group_name:
        # Object hasn't been grouped yet, just update this object
        return

    # Use PropertyManager to handle all the logic
    from .property_manager import get_property_manager
    prop_manager = get_property_manager()
    prop_manager.set_surface_type(context.active_object, new_surface_type_str)


class ObjectAttributes(PropertyGroup):
    isSeating: BoolProperty(name="Is Seating")
    isSurface: BoolProperty(name="Is Surface")
    surfaceType: EnumProperty(
        name="Surface Type",
        description="Type of surface",
        items=classification.SURFACE_TYPE_ITEMS,
        default=classification.SURFACE_WALL,
        update=update_surface_type,
    )
    group_name: StringProperty(
        name="Group Name",
        description="Name of the group this object belongs to",
        default="",
    )
