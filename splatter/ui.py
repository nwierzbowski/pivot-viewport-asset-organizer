from re import S
import bpy
from .operators.operators import (
    Splatter_OT_Organize_Classified_Objects,
    Splatter_OT_Upgrade_To_Pro,
)

from .operators.classification import (
    Splatter_OT_Classify_Selected,
    Splatter_OT_Classify_Active_Object,
)

from .constants import PRE, CATEGORY, LICENSE_PRO
from .classes import LABEL_OBJECTS_COLLECTION, LABEL_ROOM_COLLECTION, LABEL_SURFACE_TYPE, LABEL_LICENSE_TYPE
from .engine_state import get_engine_license_status, set_engine_license_status
from . import engine


class Splatter_PT_Status_Panel(bpy.types.Panel):
    bl_label = "Pivot Status"
    bl_idname = PRE + "_PT_status_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY  # Tab name in the N-Panel
    bl_order = 0  # Make it appear at the top

    def draw(self, context):
        layout = self.layout
        
        # Get license_type from cached engine status, sync if needed
        license_type = get_engine_license_status()
        if license_type == "UNKNOWN":
            try:
                license_type = engine.sync_license_mode()
                set_engine_license_status(license_type)
            except Exception as e:
                print(f"[Splatter] Failed to sync license: {e}")
                license_type = "UNKNOWN"
        
        # Show license selector
        self._draw_license_selector(layout, license_type)
    
    def _draw_license_selector(self, layout, license_type):
        """Draw the license type display (read-only)."""
        row = layout.row()
        row.label(text=f"License: {license_type}")


class Splatter_PT_Pro_Panel(bpy.types.Panel):
    bl_label = "Pivot Pro Operations"
    bl_idname = PRE + "_PT_pro_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY  # Tab name in the N-Panel

    def draw_header(self, context):
        row = self.layout.row()
        if get_engine_license_status() != LICENSE_PRO:
            row.label(text="", icon='LOCKED')

    def draw(self, context):
        layout = self.layout
        
        # Get license_type from cached engine status, sync if needed
        license_type = get_engine_license_status()
        if license_type == "UNKNOWN":
            try:
                license_type = engine.sync_license_mode()
                set_engine_license_status(license_type)
            except Exception as e:
                print(f"[Splatter] Failed to sync license: {e}")
                license_type = "UNKNOWN"
        
        enabled = (license_type == LICENSE_PRO)
        
        if enabled:
            # Objects Collection selector
            row = layout.row()
            row.prop(bpy.context.scene.splatter, "objects_collection")
            
            # Pro features
            row = layout.row()
            row.operator(Splatter_OT_Classify_Selected.bl_idname)
            
            # Organization button
            row = layout.row()
            row.operator(Splatter_OT_Organize_Classified_Objects.bl_idname)
        else:
            # Standard mode: show upgrade info
            layout.label(text="Unlock Your Full Pipeline:")
            layout.label(text="- Multithreaded bulk standardization")
            layout.label(text="- Auto sort assets into collections")
            layout.label(text="- Use collections to arrange viewport ")
            layout.separator()
            row = layout.row()
            row.operator(Splatter_OT_Upgrade_To_Pro.bl_idname, icon='WORLD')


class Splatter_PT_Standard_Panel(bpy.types.Panel):
    bl_label = "Pivot Standard Operations"
    bl_idname = PRE + "_PT_standard_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY  # Tab name in the N-Panel

    def draw(self, context):
        obj = context.active_object
        layout = self.layout
        
        # Classification buttons
        row = layout.row()
        row.operator(Splatter_OT_Classify_Active_Object.bl_idname)

