import sys
import bpy
import os
import stat

from splatter import engine

from .classes import SceneAttributes
from bpy.props import PointerProperty

from .operators.operators import (
    Splatter_OT_Organize_Classified_Objects,
    Splatter_OT_Upgrade_To_Pro,
)
from .operators.classification import (
    Splatter_OT_Classify_Selected,
    Splatter_OT_Classify_Active_Object,
)
from .ui import Splatter_PT_Standard_Panel, Splatter_PT_Pro_Panel, Splatter_PT_Status_Panel
from . import handlers

bl_info = {
    "name": "Splatter: AI Powered Object Scattering",
    "author": "Nick Wierzbowski",
    "version": (1, 0, 0),
    "blender": (4, 4, 0),  # Minimum Blender version
    "location": "View3D > Sidebar > Splatter",
    "description": "Performs scene segmentation, object classification, and intelligent scattering.",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

# Track if standard panel was registered (only for non-pro licenses)
_standard_panel_registered = False

classesToRegister = (
    SceneAttributes,
    Splatter_PT_Status_Panel,
    Splatter_PT_Pro_Panel,
    Splatter_OT_Classify_Selected,
    Splatter_OT_Classify_Active_Object,
    Splatter_OT_Organize_Classified_Objects,
    Splatter_OT_Upgrade_To_Pro,
)


def register():
    global _standard_panel_registered
    print(f"Registering {bl_info.get('name')} version {bl_info.get('version')}")
    for cls in classesToRegister:
        bpy.utils.register_class(cls)
    bpy.types.Scene.splatter = PointerProperty(type=SceneAttributes)

    # Ensure engine binary is executable after zip install (zip extraction often drops exec bits)
    try:
        engine_path = os.path.join(os.path.dirname(__file__), 'bin', 'splatter_engine')
        if os.path.exists(engine_path) and os.name != 'nt':
            st = os.stat(engine_path)
            if not (st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                os.chmod(engine_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print("Fixed executable permissions on splatter engine binary (register)")
    except Exception as e:
        print(f"Note: Could not adjust permissions for engine binary during register: {e}")

    # Start the splatter engine
    engine_started = engine.start_engine()
    
    if not engine_started:
        print("[Splatter] Failed to start engine after loading file")
        is_pro = False  # Default to standard if engine fails
    else:
        # Print Cython edition for debugging
        try:
            lib_path = os.path.join(os.path.dirname(__file__), 'lib')
            if lib_path not in sys.path:
                sys.path.insert(0, lib_path)
            from .lib import edition_utils
            edition_utils.print_edition()
            is_pro = edition_utils.is_pro_edition()
        except Exception as e:
            print(f"[Splatter] Could not print Cython edition: {e}")
            is_pro = False

    # Conditionally register standard panel for non-pro licenses
    if not is_pro:
        bpy.utils.register_class(Splatter_PT_Standard_Panel)
        _standard_panel_registered = True

    # Register persistent handlers for engine lifecycle management
    if handlers.on_load_pre not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(handlers.on_load_pre)
    if handlers.on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(handlers.on_load_post)
    
    # Only register depsgraph update handler for Pro edition
    if is_pro:
        if handlers.on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(handlers.on_depsgraph_update)

    


def unregister():
    global _standard_panel_registered
    print(f"Unregistering {bl_info.get('name')}")
    for cls in reversed(classesToRegister):  # Unregister in reverse order
        bpy.utils.unregister_class(cls)

    # Conditionally unregister standard panel if it was registered
    if _standard_panel_registered:
        bpy.utils.unregister_class(Splatter_PT_Standard_Panel)
        _standard_panel_registered = False

    del bpy.types.Scene.splatter

    # Unregister all persistent handlers
    if handlers.on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(handlers.on_load_pre)
    if handlers.on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(handlers.on_load_post)
    # Only remove depsgraph update handler if it's registered (was only added for Pro edition)
    if handlers.on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(handlers.on_depsgraph_update)

    # Perform cleanup as if we're unloading a file
    handlers.on_load_pre(None)
    engine.stop_engine()


if __name__ == "__main__":
    register()
