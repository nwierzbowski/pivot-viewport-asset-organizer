# Property Management System
# Centralized management of object properties with automatic engine synchronization

class PropertyManager:
    """Centralized manager for object properties that handles engine synchronization."""

    def __init__(self):
        self._engine_communicator = None

    def _get_engine_communicator(self):
        """Lazy initialization of engine communicator."""
        if self._engine_communicator is None:
            try:
                from .engine import get_engine_communicator
                self._engine_communicator = get_engine_communicator()
            except RuntimeError:
                self._engine_communicator = None
        return self._engine_communicator

    def set_surface_type(self, obj, surface_type, update_group=True, update_engine=True):
        """
        Set surface type for an object with optional group and engine updates.

        Args:
            obj: Blender object
            surface_type: Surface type value (string for Blender, int for engine)
            update_group: Whether to update all objects in the same group
            update_engine: Whether to sync with the engine
        """
        if not hasattr(obj, 'classification'):
            return False

        # Convert to appropriate types
        surface_type_str = str(surface_type)
        try:
            surface_type_int = int(surface_type)
        except (ValueError, TypeError):
            return False

        group_name = obj.classification.group_name

        # If this is a group update and we should update the engine, send group command
        if update_group and update_engine and group_name:
            engine = self._get_engine_communicator()
            if engine:
                try:
                    command = {
                        "id": 2,
                        "op": "set_group_attr",
                        "group_name": group_name,
                        "attr": "surface_type",
                        "value": surface_type_int
                    }

                    response = engine.send_command(command)
                    if "ok" not in response or not response["ok"]:
                        print(f"Failed to update engine group surface type: {response.get('error', 'Unknown error')}")
                        return False
                except Exception as e:
                    print(f"Error updating engine group: {e}")
                    return False

        # Update the object's property
        if obj.classification.surfaceType != surface_type_str:
            obj.classification.surfaceType = surface_type_str

        # Update group if requested
        if update_group and group_name:
            self._update_group_surface_type(obj, surface_type_str, surface_type_int)
            # Update expected engine state for the group
            self._update_group_engine_state(group_name, surface_type_int)
        elif update_engine:
            # Single object update - update the group's expected state
            if group_name:
                self._update_engine_state(group_name, surface_type_int)

        return True

    def set_group_name(self, obj, group_name):
        """Set group name for an object."""
        if hasattr(obj, 'classification'):
            obj.classification.group_name = group_name
            return True
        return False

    def _update_engine_state(self, group_name, surface_type_int):
        """Update the expected engine state for a group."""
        from . import engine_state
        engine_state._engine_expected_state[group_name] = surface_type_int

    def _update_group_engine_state(self, group_name, surface_type_int):
        """Update the expected engine state for a group."""
        self._update_engine_state(group_name, surface_type_int)

    def _update_group_surface_type(self, source_obj, surface_type_str, surface_type_int):
        """Update all objects in the same group as the source object."""
        import bpy

        group_name = source_obj.classification.group_name
        if not group_name:
            return

        # Update all other objects in the group (skip the source object)
        for obj in bpy.context.scene.objects:
            if (obj != source_obj and
                hasattr(obj, 'classification') and
                hasattr(obj.classification, 'group_name') and
                obj.classification.group_name == group_name):

                # Update the property directly to avoid triggering callbacks
                if obj.classification.surfaceType != surface_type_str:
                    obj.classification.surfaceType = surface_type_str

    def sync_object_with_engine(self, obj):
        """
        Sync a single object's surface type with the engine.
        Returns True if sync was successful.
        """
        if not (hasattr(obj, 'classification') and
                hasattr(obj.classification, 'group_name') and
                obj.classification.group_name):
            return False

        engine = self._get_engine_communicator()
        if not engine:
            return False

        try:
            group_name = obj.classification.group_name
            surface_type = int(obj.classification.surfaceType)

            command = {
                "id": 3,
                "op": "set_group_attr",
                "group_name": group_name,
                "attr": "surface_type",
                "value": surface_type
            }

            response = engine.send_command(command)
            if response.get("ok"):
                self._update_engine_state(group_name, surface_type)
                return True
            else:
                print(f"Failed to sync {obj.name}: {response.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"Error syncing {obj.name}: {e}")

        return False

    def needs_surface_sync(self, obj):
        """Check if an object needs surface type synchronization."""
        if not (hasattr(obj, 'classification') and
                hasattr(obj.classification, 'group_name') and
                hasattr(obj.classification, 'surfaceType')):
            return False

        # Only sync objects that have been processed by align_to_axes
        if not obj.classification.group_name:
            return False

        try:
            current_type = int(obj.classification.surfaceType)
            from . import engine_state
            expected_type = engine_state._engine_expected_state.get(obj.classification.group_name)
            return expected_type is not None and current_type != expected_type
        except (ValueError, AttributeError):
            return False


# Global instance
_property_manager = PropertyManager()

def get_property_manager():
    """Get the global property manager instance."""
    return _property_manager
