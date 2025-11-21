import bpy
import time

from ..constants import PRE, FINISHED
from ..lib import standardize
from ..lib import group_manager
from .. import engine_state
from ..classification_utils import get_qualifying_objects_for_selected, selected_has_qualifying_objects


class Pivot_OT_Standardize_Selected_Groups(bpy.types.Operator):
    """
    Pro Edition: Standardize Selected Groups
    
    Takes user selection, groups objects by collection boundaries and root parents,
    performs classification on entire groups with group guessing in the engine.
    """
    bl_idname = "object." + PRE.lower() + "standardize_selected_groups"
    bl_icon = 'OUTLINER_COLLECTION'
    license_type = engine_state.get_engine_license_status()
    bl_label = "Standardize & Classify Selected Groups"
    bl_description = "Analyzes the selection to identify asset groups in the Source Collection. Runs the full standardization and classification process on each group, then creates a new, perfectly organized Outliner structure. This is the main 'processing' step for your scene"
    bl_options = {"REGISTER", "UNDO"}
    

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        return selected_has_qualifying_objects(sel, objects_collection)

    def execute(self, context):
        # Exit edit mode if active to ensure mesh data is accessible
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        startTime = time.perf_counter()
        
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        objects = get_qualifying_objects_for_selected(context.selected_objects, objects_collection)
        standardize.standardize_groups(objects)
        
        endTime = time.perf_counter()
        elapsed = endTime - startTime
        print(f"Standardize Selected Groups completed in {(elapsed) * 1000:.2f}ms")
        engine_state._is_performing_classification = True
        return {FINISHED}