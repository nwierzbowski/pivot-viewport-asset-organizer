from re import S
import bpy
from .operators import (
    Splatter_OT_Classify_Object,
    Splatter_OT_Generate_Base,
    Splatter_OT_Segment_Scene,
    Splatter_OT_Classify_Base,
)

from .constants import PRE, CATEGORY


class Splatter_PT_Main_Panel(bpy.types.Panel):
    bl_label = "Splatter Operations"
    bl_idname = PRE + "_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY  # Tab name in the N-Panel

    def draw(self, context):
        obj = context.active_object

        layout = self.layout
        layout.label(text="Deep Learning Operations:")
        layout.operator(
            Splatter_OT_Segment_Scene.bl_idname, text="Segment Current Scene"
        )
        # Add more operators here later
        layout.separator()
        layout.label(text="Room Generation:")
        layout.operator(
            Splatter_OT_Generate_Base.bl_idname, text=Splatter_OT_Generate_Base.bl_label
        )
        layout.operator(
            Splatter_OT_Classify_Base.bl_idname, text=Splatter_OT_Classify_Base.bl_label
        )
        layout.separator()
        layout.label(text="Object Classification:")
        layout.operator(
            Splatter_OT_Classify_Object.bl_idname,
            text=Splatter_OT_Classify_Object.bl_label,
        )
        layout.separator()
        layout.label(text="Object Analysis:")

        if obj:
            try:
                if hasattr(obj, "classification"):
                    c = obj.classification
                    layout.prop(c, "isSeating", text="Is Seating")
                    layout.prop(c, "isSurface", text="Is Surface")
            except (AttributeError, ReferenceError, MemoryError) as e:
                # Silently handle the error or show a message
                layout.label(text="Classification data not available")
