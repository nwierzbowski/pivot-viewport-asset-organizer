# type: ignore
from bpy.types import PropertyGroup, Collection
from bpy.props import BoolProperty, EnumProperty, StringProperty, PointerProperty

# Import C enum values from Cython module
from .lib import classification



def update_property(self, context, prop_name):
    """Generic callback that runs when any syncable property is changed"""
    

    # Only run callback if this object is the active object (user-initiated change)
    if self.id_data != bpy.context.active_object:
        return

    blender_value = getattr(self, prop_name)
    group_name = self.group_name

    if not group_name:
        # Object hasn't been grouped yet, just update this object
        return

    # Use PropertyManager to handle all the logic
    from .property_manager import get_property_manager
    prop_manager = get_property_manager()
    prop_manager.set_attribute(context.active_object, prop_name, blender_value)


class SceneAttributes(PropertyGroup):
    objects_collection: PointerProperty(
        name="Objects Collection",
        description="Collection containing objects to scatter",
        type=Collection,
    )
    room_collection: PointerProperty(
        name="Room Collection",
        description="Collection containing room geometry",
        type=Collection,
    )


class ObjectAttributes(PropertyGroup):
    # isSeating: BoolProperty(name="Is Seating")
    # isSurface: BoolProperty(name="Is Surface")
    surface_type: EnumProperty(
        name="Surface Type",
        description="Type of surface",
        items=classification.SURFACE_TYPE_ITEMS,
        default=classification.SURFACE_WALL,
        update=lambda self, context: update_property(self, context, 'surface_type'),
    )
    group_name: StringProperty(
        name="Group Name",
        description="Name of the group this object belongs to",
        default="",
    )
