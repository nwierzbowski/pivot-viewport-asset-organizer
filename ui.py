import bpy
from .operators import Splatter_OT_Generate_Room, Splatter_OT_Segment_Scene

from .constants import PRE, CATEGORY


class Splatter_PT_Main_Panel(bpy.types.Panel):
    bl_label = "Splatter Operations"
    bl_idname = PRE + "_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY  # Tab name in the N-Panel

    def draw(self, context):
        layout = self.layout
        layout.label(text="Deep Learning Operations:")
        layout.operator(
            Splatter_OT_Segment_Scene.bl_idname, text="Segment Current Scene"
        )
        # Add more operators here later
        layout.separator()
        layout.label(text="Room Generation:")
        layout.operator(Splatter_OT_Generate_Room.bl_idname, text="Generate Base")
