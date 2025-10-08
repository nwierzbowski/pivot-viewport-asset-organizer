from re import S
import bpy
from .operators import (
    Splatter_OT_Classify_Selected_Objects,
    Splatter_OT_Classify_All_Objects_In_Collection,
    Splatter_OT_Organize_Classified_Objects,
    Splatter_OT_Classify_Object,
    Splatter_OT_Selection_To_Seating,
    Splatter_OT_Selection_To_Surfaces,
    Splatter_OT_Classify_Faces,
    Splatter_OT_Generate_Base,
    Splatter_OT_Classify_Base,
    Splatter_OT_Select_Surfaces,
    Splatter_OT_Select_Seating,
)

from .constants import PRE, CATEGORY, LICENSE_PRO
from .classes import LABEL_OBJECTS_COLLECTION, LABEL_ROOM_COLLECTION, LABEL_SURFACE_TYPE, LABEL_LICENSE_TYPE
from .engine_state import get_engine_license_status, set_engine_license_status
from . import engine


class Splatter_PT_Main_Panel(bpy.types.Panel):
    bl_label = "Splatter Operations"
    bl_idname = PRE + "_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY  # Tab name in the N-Panel

    def draw(self, context):
        obj = context.active_object
        layout = self.layout
        scene = context.scene
        
        # Get license_type from cached engine status, sync if needed
        match, license_type = get_engine_license_status()
        if license_type == "UNKNOWN":
            try:
                match, license_type = engine.sync_license_mode()
                set_engine_license_status(match, license_type)
            except Exception as e:
                print(f"[Splatter] Failed to sync license: {e}")
                license_type = "UNKNOWN"
        
        # Always show license selector
        self._draw_license_selector(layout, license_type)
        
        layout.separator()
        
        if license_type == LICENSE_PRO:
            self._draw_pro_ui(layout, obj)
        else:
            self._draw_standard_ui(layout)
    
    def _draw_license_selector(self, layout, license_type):
        """Draw the license type display (read-only)."""
        row = layout.row()
        row.label(text=f"License: {license_type}")
    
    def _draw_standard_ui(self, layout):
        """Draw the standard license UI - minimal functionality."""
        # Classification buttons
        row = layout.row()
        row.operator(Splatter_OT_Classify_Selected_Objects.bl_idname)
    
    def _draw_pro_ui(self, layout, obj):
        """Draw the pro license UI - full functionality."""
        # Objects Collection selector
        row = layout.row()
        row.prop(bpy.context.scene.splatter, "objects_collection")
        
        # Object classification controls (if applicable)
        self._draw_object_controls(layout, obj)
        
        layout.separator()
        
        # Classification buttons
        row = layout.row()
        row.operator(Splatter_OT_Classify_Selected_Objects.bl_idname)
        row.operator(Splatter_OT_Classify_All_Objects_In_Collection.bl_idname)
        
        # Organization button
        layout.operator(Splatter_OT_Organize_Classified_Objects.bl_idname)
    
    def _draw_object_controls(self, layout, obj):
        """Draw object-specific classification controls."""
        if not obj:
            return
            
        try:
            c = obj.classification
            if not c.group_name:
                layout.label(text="Classify object first")
            else:
                row = layout.row()
                row.prop(c, "surface_type")
        except (AttributeError, ReferenceError, MemoryError) as e:
            layout.label(text="Classification data not available")
