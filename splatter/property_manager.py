# Property Management System
# Centralized management of object properties with automatic engine synchronization

import bpy
from typing import Any, Optional

from . import engine_state

# Command IDs for engine communication
COMMAND_SET_GROUP_ATTR = 2
COMMAND_SYNC_OBJECT = 3


class PropertyManager:
    """Centralized manager for object properties that handles engine synchronization."""

    def __init__(self) -> None:
        self._engine_communicator: Optional[Any] = None

    def _get_engine_communicator(self) -> Optional[Any]:
        """Lazy initialization of engine communicator."""
        if self._engine_communicator is None:
            try:
                from .engine import get_engine_communicator
                self._engine_communicator = get_engine_communicator()
            except RuntimeError:
                self._engine_communicator = None
        return self._engine_communicator

    def set_surface_type(self, obj: Any, surface_type: Any, update_group: bool = True, update_engine: bool = True) -> bool:
        """
        Set surface type for an object with optional group and engine updates.

        Args:
            obj: Blender object.
            surface_type: Surface type value (string for Blender, int for engine).
            update_group: Whether to update all objects in the same group.
            update_engine: Whether to sync with the engine.

        Returns:
            bool: True if successful, False otherwise.
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

        # Handle group update with engine sync
        if update_group and update_engine and group_name:
            if not self._send_group_surface_type_command(group_name, surface_type_int):
                return False

        # Update the object's property
        if obj.classification.surfaceType != surface_type_str:
            obj.classification.surfaceType = surface_type_str

        # Update group properties if requested
        if update_group and group_name:
            self._update_group_surface_type(obj, surface_type_str, surface_type_int)
            self._update_engine_state(group_name, surface_type_int)
        elif update_engine and group_name:
            # Single object update - update the group's expected state
            self._update_engine_state(group_name, surface_type_int)

        return True

    def _send_group_surface_type_command(self, group_name: str, surface_type_int: int) -> bool:
        """Send command to engine to set group surface type."""
        engine = self._get_engine_communicator()
        if not engine:
            return False

        try:
            command = {
                "id": COMMAND_SET_GROUP_ATTR,
                "op": "set_group_attr",
                "group_name": group_name,
                "attr": "surface_type",
                "value": surface_type_int
            }
            response = engine.send_command(command)
            if "ok" not in response or not response["ok"]:
                print(f"Failed to update engine group surface type: {response.get('error', 'Unknown error')}")
                return False
            return True
        except Exception as e:
            print(f"Error updating engine group: {e}")
            return False

    def set_group_name(self, obj: Any, group_name: str) -> bool:
        """Set group name for an object.

        Args:
            obj: Blender object.
            group_name: Name of the group.

        Returns:
            bool: True if successful, False otherwise.
        """
        if hasattr(obj, 'classification'):
            obj.classification.group_name = group_name
            return True
        return False

    def _update_engine_state(self, group_name: str, surface_type_int: int) -> None:
        """Update the expected engine state for a group.

        Args:
            group_name: Name of the group.
            surface_type_int: Surface type as integer.
        """
        engine_state._engine_expected_state[group_name] = surface_type_int

    def _update_group_surface_type(self, source_obj: Any, surface_type_str: str, surface_type_int: int) -> None:
        """Update all objects in the same group as the source object.

        Args:
            source_obj: The source Blender object.
            surface_type_str: Surface type as string.
            surface_type_int: Surface type as integer (unused here).
        """
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

    def sync_object_with_engine(self, obj: Any) -> bool:
        """
        Sync a single object's surface type with the engine.

        Args:
            obj: Blender object.

        Returns:
            bool: True if sync was successful, False otherwise.
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
                "id": COMMAND_SYNC_OBJECT,
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

    def needs_surface_sync(self, obj: Any) -> bool:
        """Check if an object needs surface type synchronization.

        Args:
            obj: Blender object.

        Returns:
            bool: True if sync is needed, False otherwise.
        """
        if not (hasattr(obj, 'classification') and
                hasattr(obj.classification, 'group_name') and
                hasattr(obj.classification, 'surfaceType')):
            return False

        # Only sync objects that have been processed by align_to_axes
        if not obj.classification.group_name:
            return False

        try:
            current_type = int(obj.classification.surfaceType)
            expected_type = engine_state._engine_expected_state.get(obj.classification.group_name)
            return expected_type is not None and current_type != expected_type
        except (ValueError, AttributeError):
            return False


# Global instance
_property_manager = PropertyManager()

def get_property_manager() -> PropertyManager:
    """Get the global property manager instance."""
    return _property_manager
