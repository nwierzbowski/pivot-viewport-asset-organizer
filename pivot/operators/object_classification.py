import bpy
import time

from ..constants import PRE, FINISHED
from ..lib import standardize
from ..classification_utils import get_qualifying_objects_for_selected, selected_has_qualifying_objects

# Operator descriptions
# DESC_STANDARDIZE_SELECTED = "Performs the complete standardization process on each selected object. It first determines the 'Surface Context', then applies the chosen 'Origin Method' and the 'Align Facing' rotation."
DESC_SET_ORIGIN_SELECTED = "Applies the configured 'Origin Method' to each selected object, respecting the chosen 'Surface Context'. Use this to fix only the origins without affecting rotation"
DESC_ALIGN_FACING_SELECTED = "Applies the 'Align Facing' rotation to each selected object, respecting the chosen 'Surface Context' to determine the correct 'forward' direction"
# DESC_STANDARDIZE_ACTIVE = "Performs the complete standardization process on the active object. It first determines the 'Surface Context', then applies the chosen 'Origin Method' and the 'Align Facing' rotation"
DESC_SET_ORIGIN_ACTIVE = "Applies the configured 'Origin Method' to the active object, respecting the chosen 'Surface Context'. Use this to fix only the origins without affecting rotation"
DESC_ALIGN_FACING_ACTIVE = "Applies the 'Align Facing' rotation to the active object, respecting the chosen 'Surface Context' to determine the correct 'forward' direction"


# def _standardize_objects(objects, operation_name):
#     """Helper function to standardize objects and log timing."""
#     # Exit edit mode if active to ensure mesh data is accessible
#     if bpy.context.mode == 'EDIT_MESH':
#         bpy.ops.object.mode_set(mode='OBJECT')
    
#     startTime = time.perf_counter()
    
#     standardize.standardize_objects(objects)
    
#     endTime = time.perf_counter()
#     elapsed = endTime - startTime
#     print(f"{operation_name} completed in {(elapsed) * 1000:.2f}ms")


def _set_origin_objects(objects, operation_name):
    """Helper function to set origin for objects and log timing."""
    # Exit edit mode if active to ensure mesh data is accessible
    if bpy.context.mode == 'EDIT_MESH':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    startTime = time.perf_counter()
    
    standardize.set_origin_objects(objects)
    
    endTime = time.perf_counter()
    elapsed = endTime - startTime
    print(f"{operation_name} completed in {(elapsed) * 1000:.2f}ms")


def _align_facing_objects(objects, operation_name):
    """Helper function to align facing for objects and log timing."""
    # Exit edit mode if active to ensure mesh data is accessible
    if bpy.context.mode == 'EDIT_MESH':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    startTime = time.perf_counter()
    
    standardize.align_facing_objects(objects)
    
    endTime = time.perf_counter()
    elapsed = endTime - startTime
    print(f"{operation_name} completed in {(elapsed) * 1000:.2f}ms")


# class Pivot_OT_Standardize_Selected_Objects(bpy.types.Operator):
#     """
#     Pro Edition: Standardize Selected Objects
    
#     Standardizes one or more selected objects.
#     """
#     bl_idname = "object." + PRE.lower() + "standardize_selected_objects"
#     bl_label = "Full Standardization"
#     bl_description = DESC_STANDARDIZE_SELECTED
#     bl_options = {"REGISTER", "UNDO"}
#     bl_icon = 'OBJECT_DATA'

#     @classmethod
#     def poll(cls, context):
#         sel = getattr(context, "selected_objects", None) or []
#         scene_collection = getattr(context.scene, "collection", None)
#         if not scene_collection:
#             return False
#         return selected_has_qualifying_objects(sel, scene_collection)

#     def execute(self, context):
#         scene_collection = getattr(context.scene, "collection", None)
#         if not scene_collection:
#             return {FINISHED}
#         objects = get_qualifying_objects_for_selected(context.selected_objects, scene_collection)
#         _standardize_objects(objects, "Standardize Selected Objects")
#         return {FINISHED}


class Pivot_OT_Set_Origin_Selected_Objects(bpy.types.Operator):
    """
    Pro Edition: Set Origin Selected Objects
    
    Sets origin for one or more selected objects.
    """
    bl_idname = "object." + PRE.lower() + "set_origin_selected_objects"
    bl_label = "Set Object Origin"
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
        _set_origin_objects(objects, "Set Origin Selected Objects")
        return {FINISHED}


class Pivot_OT_Align_Facing_Selected_Objects(bpy.types.Operator):
    """
    Pro Edition: Align Facing Selected Objects
    
    Aligns facing for one or more selected objects.
    """
    bl_idname = "object." + PRE.lower() + "align_facing_selected_objects"
    bl_label = "Align Object Facing"
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
        _align_facing_objects(objects, "Align Facing Selected Objects")
        return {FINISHED}


# class Pivot_OT_Standardize_Active_Object(bpy.types.Operator):
#     """
#     Standard Edition: Standardize Active Object
    
#     Standardizes the active object only.
#     """
#     bl_idname = "object." + PRE.lower() + "standardize_active_object"
#     bl_label = "Full Standardization"
#     bl_description = DESC_STANDARDIZE_ACTIVE
#     bl_options = {"REGISTER", "UNDO"}
#     bl_icon = 'OBJECT_DATA'

#     @classmethod
#     def poll(cls, context):
#         obj = context.active_object
#         scene_collection = getattr(context.scene, "collection", None)
#         if not obj or not scene_collection:
#             return False
#         return selected_has_qualifying_objects([obj], scene_collection)

#     def execute(self, context):
#         scene_collection = getattr(context.scene, "collection", None)
#         obj = context.active_object
#         if not scene_collection:
#             return {FINISHED}
#         if obj and obj in get_qualifying_objects_for_selected([obj], scene_collection):
#             _standardize_objects([obj], "Standardize Active Object")
#         return {FINISHED}


class Pivot_OT_Set_Origin_Active_Object(bpy.types.Operator):
    """
    Standard Edition: Set Origin Active Object
    
    Sets origin for the active object only.
    """
    bl_idname = "object." + PRE.lower() + "set_origin_active_object"
    bl_label = "Set Object Origin"
    bl_description = DESC_SET_ORIGIN_ACTIVE
    bl_options = {"REGISTER", "UNDO"}
    bl_icon = 'OBJECT_DATA'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        scene_collection = getattr(context.scene, "collection", None)
        if not obj or not scene_collection or obj not in context.selected_objects:
            return False
        return selected_has_qualifying_objects([obj], scene_collection)

    def execute(self, context):
        scene_collection = getattr(context.scene, "collection", None)
        obj = context.active_object
        if not scene_collection:
            return {FINISHED}
        if obj and obj in get_qualifying_objects_for_selected([obj], scene_collection):
            _set_origin_objects([obj], "Set Origin Active Object")
        return {FINISHED}


class Pivot_OT_Align_Facing_Active_Object(bpy.types.Operator):
    """
    Standard Edition: Align Facing Active Object
    
    Aligns facing for the active object only.
    """
    bl_idname = "object." + PRE.lower() + "align_facing_active_object"
    bl_label = "Align Object Facing"
    bl_description = DESC_ALIGN_FACING_ACTIVE
    bl_options = {"REGISTER", "UNDO"}
    bl_icon = 'OBJECT_DATA'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        scene_collection = getattr(context.scene, "collection", None)
        if not obj or not scene_collection or obj not in context.selected_objects:
            return False
        return selected_has_qualifying_objects([obj], scene_collection)

    def execute(self, context):
        scene_collection = getattr(context.scene, "collection", None)
        obj = context.active_object
        if not scene_collection:
            return {FINISHED}
        if obj and obj in get_qualifying_objects_for_selected([obj], scene_collection):
            _align_facing_objects([obj], "Align Facing Active Object")
        return {FINISHED}