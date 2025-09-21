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

    # Convert string identifier to integer for engine
    try:
        new_surface_type = int(new_surface_type_str)
    except ValueError:
        print(f"Invalid surface type string: {new_surface_type_str}")
        return

    # Send command to engine to update the group's surface type
    try:
        from splatter.engine import get_engine_communicator
        engine = get_engine_communicator()

        command = {
            "id": 2,  # Use a different ID than align_to_axes_batch
            "op": "set_group_attr",
            "group_name": group_name,
            "attr": "surface_type",
            "value": new_surface_type
        }

        response = engine.send_command(command)
        if "ok" not in response or not response["ok"]:
            print(f"Failed to update engine group surface type: {response.get('error', 'Unknown error')}")
            return

        # Update our expected engine state for this object
        from . import _engine_expected_state
        _engine_expected_state[self.id_data.name] = new_surface_type

    except Exception as e:
        print(f"Error updating engine: {e}")
        return

    # Update all other objects in the same group (suppress their callbacks)
    import bpy
    for obj in bpy.context.scene.objects:
        if (hasattr(obj, 'classification') and
            hasattr(obj.classification, 'group_name') and
            obj.classification.group_name == group_name and
            obj != context.active_object):
            obj.classification.surfaceType = new_surface_type_str
            # Update expected state for programmatically changed objects too
            from . import _engine_expected_state
            _engine_expected_state[obj.name] = new_surface_type

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
