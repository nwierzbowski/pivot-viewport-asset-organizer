# Copyright (C) 2025 [Nicholas Wierzbowski/Elbo Studio]

# This file is part of the Pivot Bridge for Blender.

# The Pivot Bridge for Blender is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses>.

import bpy
import os
import stat

from elbo_sdk import engine
from pivot_lib import engine_state
from .classes import SceneAttributes
from bpy.props import PointerProperty

from pivot_lib import group_manager
from . import handlers
from .operators.operators import (
    Pivot_OT_Organize_Classified_Objects,
    Pivot_OT_Reset_Classifications,
    Pivot_OT_Upgrade_To_Pro,
)
from .operators.group_classification import Pivot_OT_Standardize_Selected_Groups
from .operators.object_classification import (
    Pivot_OT_Set_Origin_Selected_Objects,
    Pivot_OT_Align_Facing_Selected_Objects,
)
from .ui import Pivot_PT_Standard_Panel, Pivot_PT_Pro_Panel, Pivot_PT_Status_Panel, Pivot_PT_Configuration_Panel

classesToRegister = (
    SceneAttributes,
    Pivot_OT_Standardize_Selected_Groups,
    # Pivot_OT_Set_Origin_Selected_Groups,
    # Pivot_OT_Align_Facing_Selected_Groups,
    Pivot_OT_Set_Origin_Selected_Objects,
    Pivot_OT_Align_Facing_Selected_Objects,
    Pivot_OT_Organize_Classified_Objects,
    Pivot_OT_Reset_Classifications,
    Pivot_OT_Upgrade_To_Pro,
)

def _reset_sync_state() -> None:
    """Clear cached engine sync data so reloads start from scratch."""
    group_mgr = group_manager.get_group_manager()
    group_mgr.reset_state()
    engine_state.update_group_membership_snapshot({}, replace=True)
    handlers.clear_previous_scales()


def _register_bpy_class(cls):
    try:
        bpy.utils.register_class(cls)
    except ValueError as exc:
        message = str(exc)
        if "already registered" in message:
            print(f"[Pivot] {cls.__name__} already registered, skipping")
            return
        raise


def _unregister_bpy_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError as exc:
        message = str(exc)
        if "not registered" in message:
            print(f"[Pivot] {cls.__name__} was not registered, skipping")
            return
        raise


def _assign_scene_property() -> None:
    if hasattr(bpy.types.Scene, "pivot"):
        delattr(bpy.types.Scene, "pivot")
    bpy.types.Scene.pivot = PointerProperty(type=SceneAttributes)


def _remove_scene_property() -> None:
    if hasattr(bpy.types.Scene, "pivot"):
        delattr(bpy.types.Scene, "pivot")


def register():
    print("App Sandbox:", os.getenv("APP_SANDBOX_CONTAINER_ID"))
    print("Registering Pivot")
    
    # Stop any running engine from previous edition
    try:
        engine.stop()
    except Exception as e:
        print(f"[Pivot] Note: Could not stop engine during register: {e}")
    
    for cls in classesToRegister:
        _register_bpy_class(cls)
    _assign_scene_property()

    # Ensure engine binary is executable after zip install (zip extraction often drops exec bits)
    # Keep Blender path/layout knowledge in the bridge; elbo-sdk stays host-agnostic.
    try:
        exe_name = "pivot_engine.exe" if os.name == "nt" else "pivot_engine"
        pivot_dir = os.path.dirname(__file__)
        bin_dir = os.path.join(pivot_dir, "bin")
        platform_dir = os.path.join(bin_dir, engine.get_platform_id())
        engine_path = os.path.join(platform_dir, exe_name)
        if not os.path.exists(engine_path):
            engine_path = os.path.join(bin_dir, exe_name)

        if engine_path:
            os.environ["PIVOT_ENGINE_PATH"] = engine_path

        if engine_path and os.path.exists(engine_path) and os.name != 'nt':
            st = os.stat(engine_path)
            if not (st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                os.chmod(engine_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print("Fixed executable permissions on pivot engine binary (register)")
    except Exception as e:
        print(f"Note: Could not adjust permissions for engine binary during register: {e}")

    is_pro = False
    try:
        # Print Cython edition for debugging
        try:
            from pivot_lib import edition_utils
            edition_utils.print_edition()
            is_pro = edition_utils.is_pro_edition()
        except Exception as e:
            print(f"[Pivot] Could not print Cython edition: {e}")
            is_pro = False
    except RuntimeError as exc:
        print(f"[Pivot] Failed to start engine after loading file: {exc}")

    # Register name change callback for group management
    try:
        group_mgr = group_manager.get_group_manager()
        group_mgr.set_name_change_callback(handlers.on_group_name_changed)
    except Exception as e:
        print(f"[Pivot] Could not set group name change callback: {e}")

    _register_bpy_class(Pivot_PT_Status_Panel)
    _register_bpy_class(Pivot_PT_Configuration_Panel)

    # Always register standard panel
    _register_bpy_class(Pivot_PT_Standard_Panel)

    _register_bpy_class(Pivot_PT_Pro_Panel)

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
    print("Unregistering Pivot")
    
    _unregister_bpy_class(Pivot_PT_Pro_Panel)
    _unregister_bpy_class(Pivot_PT_Standard_Panel)
    _unregister_bpy_class(Pivot_PT_Status_Panel)
    _unregister_bpy_class(Pivot_PT_Configuration_Panel)
    
    for cls in reversed(classesToRegister):  # Unregister in reverse order
        _unregister_bpy_class(cls)

    _remove_scene_property()

    # Unregister all persistent handlers
    if handlers.on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(handlers.on_load_pre)
    if handlers.on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(handlers.on_load_post)
    # Only remove depsgraph update handler if it's registered (was only added for Pro edition)
    if handlers.on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(handlers.on_depsgraph_update)

    # Perform cleanup as if we're unloading a file
    _reset_sync_state()
    handlers.on_load_pre(None)
    engine.stop()


if __name__ == "__main__":
    register()
