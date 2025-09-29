from re import S
import bpy
from .operators import (
    Splatter_OT_Classify_Selected_Objects,
    Splatter_OT_Organize_Classified_Objects,
    Splatter_OT_Classify_Object,
    Splatter_OT_Selection_To_Seating,
    Splatter_OT_Selection_To_Surfaces,
    Splatter_OT_Classify_Faces,
    Splatter_OT_Generate_Base,
    Splatter_OT_Segment_Scene,
    Splatter_OT_Classify_Base,
    Splatter_OT_Select_Surfaces,
    Splatter_OT_Select_Seating,
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
        layout.prop(context.scene.splatter, "objects_collection")
        layout.prop(context.scene.splatter, "room_collection")
        layout.separator()
        layout.label(text="Deep Learning Operations:")
        layout.operator(
            Splatter_OT_Segment_Scene.bl_idname
        )
        # Add more operators here later
        layout.separator()
        layout.label(text="Room Generation:")
        layout.operator(
            Splatter_OT_Generate_Base.bl_idname
        )
        layout.operator(
            Splatter_OT_Classify_Base.bl_idname
        )
        layout.separator()
        layout.label(text="Surface Classification:")
        layout.operator(
            Splatter_OT_Classify_Faces.bl_idname
        )
        row = layout.row()
        row.operator(
            Splatter_OT_Select_Surfaces.bl_idname
        )
        row.operator(
            Splatter_OT_Selection_To_Surfaces.bl_idname
        )
        row = layout.row()
        row.operator(
            Splatter_OT_Select_Seating.bl_idname
        )
        row.operator(
            Splatter_OT_Selection_To_Seating.bl_idname
        )
        layout.separator()
        layout.label(text="Object Analysis:")
        layout.operator(
            Splatter_OT_Classify_Object.bl_idname
        )
        if obj:
            try:
                c = obj.classification
                # Only show classification controls if the object has been processed by classify_selected_objects
                if not c.group_name:
                    layout.label(text="Classify object first")
                else:
                    # layout.prop(c, "isSeating")
                    # layout.prop(c, "isSurface")
                    layout.prop(c, "surface_type")
            except (AttributeError, ReferenceError, MemoryError) as e:
                layout.label(text="Classification data not available")
        layout.separator()
        layout.operator(Splatter_OT_Classify_Selected_Objects.bl_idname)
        layout.operator(Splatter_OT_Organize_Classified_Objects.bl_idname)
