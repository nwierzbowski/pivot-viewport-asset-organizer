import bpy
import os
import stat
import sys

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
    Checks for geometry updates on selected mesh objects using the depsgraph.updates collection.
    """
    selected_objects = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not selected_objects:
        return

    # Iterate through all updates in the dependency graph.
    for update in depsgraph.updates:
        # Check if the geometry or transform was flagged as updated.
        if update.is_updated_geometry or update.is_updated_transform:
            for obj in selected_objects:
                # Check if the update is for this object's data block (for geometry) or the object itself (for transform).
                if update.id.original == obj.data or update.id.original == obj:
                    from .property_manager import get_property_manager
                    pm = get_property_manager()
                    group_name = pm.get_group_name(obj)
                    if group_name:
                        should_mark_unsynced = update.is_updated_geometry or (update.is_updated_transform and len(list(pm._iter_group_objects(group_name))) > 1)
                        if should_mark_unsynced:
                            pm.mark_group_unsynced(group_name)
                    break  # Found the object for this update, move to next update


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


if __name__ == "__main__":
    register()
