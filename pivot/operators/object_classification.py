import bpy
import time

from ..constants import PRE, FINISHED, LICENSE_PRO
from ..lib import standardize
from ..classification_utils import get_qualifying_objects_for_selected, selected_has_qualifying_objects
from ..engine_state import get_engine_license_status

# Operator descriptions
DESC_SET_ORIGIN_SELECTED = "Applies the configured 'Origin Method' to each selected object, respecting the chosen 'Surface Context'. Use this to fix only the origins without affecting rotation"
DESC_ALIGN_FACING_SELECTED = "Applies the 'Align Facing' rotation to each selected object, respecting the chosen 'Surface Context' to determine the correct 'forward' direction"

class Pivot_OT_Set_Origin_Selected_Objects(bpy.types.Operator):
    """
    Sets origin for one or more selected objects.
    """
    bl_idname = "object." + PRE.lower() + "set_origin_selected_objects"
    bl_label = "Standardize Object Origin"
    bl_description = DESC_SET_ORIGIN_SELECTED
    bl_options = {"REGISTER", "UNDO"}
    bl_icon = 'OBJECT_DATA'

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []
        scene_collection = getattr(context.scene, "collection", None)
        if not scene_collection:
            return False
        return selected_has_qualifying_objects(sel, scene_collection)

    def execute(self, context):
        scene_collection = getattr(context.scene, "collection", None)
        if not scene_collection:
            return {FINISHED}
        objects = get_qualifying_objects_for_selected(context.selected_objects, scene_collection)
        # Exit edit mode if active to ensure mesh data is accessible
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        startTime = time.perf_counter()
        
        license_type = get_engine_license_status()
        origin_method = context.scene.pivot.origin_method
        surface_type = context.scene.pivot.surface_type
        if license_type != LICENSE_PRO and len(objects) > 1:
            for obj in objects:
                standardize.standardize_object_origins([obj], origin_method=origin_method, surface_context=surface_type)
        else:
            standardize.standardize_object_origins(objects, origin_method=origin_method, surface_context=surface_type)
        
        endTime = time.perf_counter()
        elapsed = endTime - startTime
        print(f"Set Origin Selected Objects completed in {(elapsed) * 1000:.2f}ms")
        return {FINISHED}


class Pivot_OT_Align_Facing_Selected_Objects(bpy.types.Operator):
    """
    Aligns facing for one or more selected objects.
    """
    bl_idname = "object." + PRE.lower() + "align_facing_selected_objects"
    bl_label = "Standardize Object Rotation"
    bl_description = DESC_ALIGN_FACING_SELECTED
    bl_options = {"REGISTER", "UNDO"}
    bl_icon = 'OBJECT_DATA'

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []
        scene_collection = getattr(context.scene, "collection", None)
        if not scene_collection:
            return False
        return selected_has_qualifying_objects(sel, scene_collection)

    def execute(self, context):
        scene_collection = getattr(context.scene, "collection", None)
        if not scene_collection:
            return {FINISHED}
        objects = get_qualifying_objects_for_selected(context.selected_objects, scene_collection)
        # Exit edit mode if active to ensure mesh data is accessible
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        startTime = time.perf_counter()
        
        license_type = get_engine_license_status()
        if license_type != LICENSE_PRO and len(objects) > 1:
            for obj in objects:
                standardize.standardize_object_rotations([obj])
        else:
            standardize.standardize_object_rotations(objects)
        
        endTime = time.perf_counter()
        elapsed = endTime - startTime
        print(f"Align Facing Selected Objects completed in {(elapsed) * 1000:.2f}ms")
        return {FINISHED}

