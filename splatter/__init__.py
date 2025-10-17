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
from .group_manager import get_group_manager
from .surface_manager import get_surface_manager
from .lib import sync_manager
from . import engine_state

# Cache of each object's last-known scale to detect transform-only edits quickly.
_previous_scales: dict[str, tuple[float, float, float]] = {}

@persistent
def on_depsgraph_update_fast(scene, depsgraph):
    """Detect local changes and mark groups as out-of-sync with the engine."""
    group_mgr = get_group_manager()
    sync_mgr = sync_manager.get_sync_manager()

    current_snapshot = group_mgr.get_group_membership_snapshot()
    expected_snapshot = engine_state.get_group_membership_snapshot()
    all_groups = set(expected_snapshot) | set(current_snapshot)

    for group_name in all_groups:
        if not group_name:
            continue

        current_members = current_snapshot.get(group_name, set())
        expected_members = expected_snapshot.get(group_name)

        if expected_members is None:
            if current_members:
                sync_mgr.set_group_unsynced(group_name)
            continue

        if expected_members == current_members:
            continue

        print(
            f"[Splatter] Collection membership change detected for '{group_name}': prev={expected_members}, curr={current_members}"
        )
        sync_mgr.set_group_unsynced(group_name)

@persistent
def enforce_colors(scene, depsgraph):
    """Enforce correct color tags for group collections based on sync state."""
    sync_mgr = sync_manager.get_sync_manager()
    group_mgr = get_group_manager()
    group_mgr.update_colors(sync_mgr.get_sync_state())


@persistent
def unsync_mesh_changes(scene, depsgraph):
    sync_mgr = sync_manager.get_sync_manager()
    group_mgr = get_group_manager()
    expected_snapshot = engine_state.get_group_membership_snapshot()
    current_snapshot = group_mgr.get_group_membership_snapshot()

    selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if selected_objects:
        for update in depsgraph.updates:
            if not (update.is_updated_geometry or update.is_updated_transform):
                continue

            for obj in selected_objects:
                if update.id.original not in (obj, obj.data):
                    continue

                group_name = group_mgr.get_group_name(obj)
                if not group_name:
                    break

                expected_members = expected_snapshot.get(group_name)
                current_members = current_snapshot.get(group_name, set())
                member_count = len(expected_members) if expected_members is not None else len(current_members)

                current_scale = tuple(obj.scale)
                prev_scale = _previous_scales.get(obj.name)
                scale_changed = prev_scale is not None and current_scale != prev_scale

                should_mark_unsynced = (
                    expected_members is None
                    or update.is_updated_geometry
                    or scale_changed
                    or (update.is_updated_transform and not scale_changed and member_count > 1)
                )

                if should_mark_unsynced:
                    sync_mgr.set_group_unsynced(group_name)

                _previous_scales[obj.name] = current_scale
                break

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
    
    global _previous_scales
    _previous_scales.clear()
    engine_state.update_group_membership_snapshot({}, replace=True)

    if unsync_mesh_changes not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(unsync_mesh_changes)
    if enforce_colors not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(enforce_colors)


def unregister():
    print(f"Unregistering {bl_info.get('name')}")
    for cls in reversed(classesToRegister):  # Unregister in reverse order
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.splatter

    # Sync group classifications to engine before stopping
    try:
        surface_manager = get_surface_manager()
        classifications = surface_manager.collect_group_classifications()
        if classifications:
            surface_manager.sync_group_classifications(classifications)
    except Exception as e:
        print(f"Failed to sync classifications before closing: {e}")

    # Stop the splatter engine
    engine.stop_engine()

    # Unregister edit mode hook
    if unsync_mesh_changes in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(unsync_mesh_changes)
    if enforce_colors in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(enforce_colors)

    engine_state.update_group_membership_snapshot({}, replace=True)

    global _previous_scales
    _previous_scales.clear()


if __name__ == "__main__":
    register()
