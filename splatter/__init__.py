import bpy
import os
import stat
import sys
import hashlib

from bpy.app.handlers import persistent

from .classes import SceneAttributes
from bpy.props import PointerProperty

from .operators.operators import (
    Splatter_OT_Organize_Classified_Objects,
)
from .operators.classification import (
    Splatter_OT_Classify_Selected,
    Splatter_OT_Classify_Active_Object,
    Splatter_OT_Classify_All_Objects_In_Collection,
)
from .ui import Splatter_PT_Main_Panel
from . import engine

@persistent
def on_depsgraph_update_fast(scene, depsgraph):
    """
    Checks for geometry updates on the active object using the depsgraph.updates collection.
    """
    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        return

    # Iterate through all updates in the dependency graph.
    for update in depsgraph.updates:
        # Check if the update is for the active object's data block
        # and if the geometry was flagged as updated.
        if (update.id.original == obj.data) and update.is_updated_geometry:
            from .property_manager import get_property_manager
            pm = get_property_manager()
            group_name = pm.get_group_name(obj)
            if group_name:
                pm.mark_group_unsynced(group_name)
            break  # Exit the loop once the first matching update is found.


bl_info = {
    "name": "Splatter: AI Powered Object Scattering",
    "author": "Nick Wierzbowski",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),  # Minimum Blender version
    "location": "View3D > Sidebar > Splatter",
    "description": "Performs scene segmentation, object classification, and intelligent scattering.",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

classesToRegister = (
    SceneAttributes,
    Splatter_PT_Main_Panel,
    Splatter_OT_Classify_Selected,
    Splatter_OT_Classify_Active_Object,
    Splatter_OT_Classify_All_Objects_In_Collection,
    Splatter_OT_Organize_Classified_Objects,
)


def register():
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
        print("[Splatter] Failed to start engine")
    else:
        # Print Cython edition for debugging

        try:
            lib_path = os.path.join(os.path.dirname(__file__), 'lib')
            if lib_path not in sys.path:
                sys.path.insert(0, lib_path)
            from .lib import edition_utils
            edition_utils.print_edition()
        except Exception as e:
            print(f"[Splatter] Could not print Cython edition: {e}")
    
    # Register edit mode hook
    bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update_fast)
    
    # Example: Add addon preferences (if you create an AddonPreferences class)
    # bpy.utils.register_class(MyAddonPreferences)

    # Example: Add custom properties to Blender's scene or objects
    # bpy.types.Scene.my_addon_property = bpy.props.StringProperty(...)

    # TODO: Add logic here or call a utility function to:
    # 1. Check if Python virtual environments for DL models exist.
    # 2. If not, inform the user or provide a button (in the UI registered above)
    #    to trigger their creation and dependency installation.
    #    This setup should ideally only run once or when needed, not every time
    #    Blender starts and the addon is enabled. You might use a flag in addon prefs.


def unregister():
    print(f"Unregistering {bl_info.get('name')}")
    for cls in reversed(classesToRegister):  # Unregister in reverse order
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.splatter

    # Sync group classifications to engine before stopping
    try:
        from .property_manager import get_property_manager
        pm = get_property_manager()
        classifications = pm.collect_group_classifications()
        if classifications:
            pm.sync_group_classifications(classifications)
    except Exception as e:
        print(f"Failed to sync classifications before closing: {e}")

    # Stop the splatter engine
    engine.stop_engine()

    # Unregister edit mode hook
    bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update_fast)

    # Example: Remove addon preferences
    # bpy.utils.unregister_class(MyAddonPreferences)

    # Example: Delete custom properties
    # del bpy.types.Scene.my_addon_property


if __name__ == "__main__":
    register()
