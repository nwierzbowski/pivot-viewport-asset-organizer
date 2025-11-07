import sys
import bpy
import os
import stat
import importlib

from . import engine
from .classes import SceneAttributes
from bpy.props import PointerProperty

from .operators.operators import (
    Splatter_OT_Organize_Classified_Objects,
    Splatter_OT_Upgrade_To_Pro,
)
from .operators.classification import (
    Splatter_OT_Standardize_Selected_Groups,
    Splatter_OT_Standardize_Selected_Objects,
    Splatter_OT_Standardize_Active_Object,
)
from .ui import Splatter_PT_Standard_Panel, Splatter_PT_Pro_Panel, Splatter_PT_Status_Panel
from . import handlers

bl_info = {
    "name": "Pivot: Viewport Asset Organizer",
    "author": "Nick Wierzbowski",
    "version": (1, 0, 0),
    "blender": (4, 4, 0),  # Minimum Blender version
    "location": "View3D > Sidebar > Pivot",
    "description": "Performs viewport formatting, standardization, and grouping.",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

# Track if standard panel was registered (only for non-pro licenses)
_standard_panel_registered = False

classesToRegister = (
    SceneAttributes,
    Splatter_OT_Standardize_Selected_Groups,
    Splatter_OT_Standardize_Selected_Objects,
    Splatter_OT_Standardize_Active_Object,
    Splatter_OT_Organize_Classified_Objects,
    Splatter_OT_Upgrade_To_Pro,
)


def register():
    global _standard_panel_registered
    print(f"Registering {bl_info.get('name')} version {bl_info.get('version')}")
    
    # Stop any running engine from previous edition before reloading modules
    try:
        engine.stop_engine()
    except Exception as e:
        print(f"[Splatter] Note: Could not stop engine during register: {e}")
    
    # Force reload of Cython modules to pick up new edition binary
    cython_modules = [
        'splatter.lib.edition_utils',
        'splatter.lib.operators.classify_object',
        'splatter.lib.operators.selection_utils',
        'splatter.lib.shared.shm_utils',
        'splatter.lib.shared.transform_utils',
        'splatter.lib.shared.group_manager',
    ]
    for mod_name in cython_modules:
        if mod_name in sys.modules:
            try:
                importlib.reload(sys.modules[mod_name])
                print(f"[Splatter] Reloaded {mod_name}")
            except Exception as e:
                print(f"[Splatter] Warning: Could not reload {mod_name}: {e}")
    
    # Add platform-specific lib directory to sys.path for Cython module loading
    try:
        platform_id = engine.get_platform_id()
        addon_root = os.path.dirname(__file__)
        platform_lib_dir = os.path.join(addon_root, 'lib', platform_id)
        
        if os.path.isdir(platform_lib_dir):
            if platform_lib_dir not in sys.path:
                sys.path.insert(0, platform_lib_dir)
            print(f"[Splatter] Added platform-specific lib path: {platform_lib_dir}")
        else:
            # Fallback to root lib directory for legacy structure
            root_lib_dir = os.path.join(addon_root, 'lib')
            if root_lib_dir not in sys.path:
                sys.path.insert(0, root_lib_dir)
            print(f"[Splatter] Added legacy lib path: {root_lib_dir}")
    except Exception as e:
        print(f"[Splatter] Warning: Could not set up lib path: {e}")
    
    for cls in classesToRegister:
        bpy.utils.register_class(cls)
    bpy.types.Scene.splatter = PointerProperty(type=SceneAttributes)

    

    # Ensure engine binary is executable after zip install (zip extraction often drops exec bits)
    try:
        engine_path = engine.get_engine_binary_path()
        if engine_path and os.path.exists(engine_path) and os.name != 'nt':
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
            from .lib import edition_utils
            edition_utils.print_edition()
            is_pro = edition_utils.is_pro_edition()
        except Exception as e:
            print(f"[Splatter] Could not print Cython edition: {e}")
            is_pro = False

    bpy.utils.register_class(Splatter_PT_Status_Panel)

    # Conditionally register standard panel for non-pro licenses
    if not is_pro:
        bpy.utils.register_class(Splatter_PT_Standard_Panel)
        _standard_panel_registered = True

    bpy.utils.register_class(Splatter_PT_Pro_Panel)

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
    
    bpy.utils.unregister_class(Splatter_PT_Pro_Panel)
    if _standard_panel_registered:
        bpy.utils.unregister_class(Splatter_PT_Standard_Panel)
        _standard_panel_registered = False
    bpy.utils.unregister_class(Splatter_PT_Status_Panel)
    
    for cls in reversed(classesToRegister):  # Unregister in reverse order
        bpy.utils.unregister_class(cls)

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
