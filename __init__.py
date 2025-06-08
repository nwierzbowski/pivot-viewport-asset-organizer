import bpy

# import sys
# import importlib

# if "bpy" in locals():
#     # Make a copy of the keys to iterate over, to avoid "dictionary changed size during iteration"
#     addon_name = "Splatter - AI Powered Object Scattering"

#     # Get a list of all module names currently loaded that belong to addon
#     addon_modules_to_reload = []
#     for module_name in list(sys.modules.keys()):  # Iterate over a COPY of the keys
#         if module_name.startswith(addon_name):
#             addon_modules_to_reload.append(module_name)

#     # Now, iterate over this list and reload the modules
#     for module_name in addon_modules_to_reload:
#         try:
#             # Ensure the module is actually in sys.modules before trying to reload
#             # (It might have been removed by a previous reload/unregister, though unlikely here)
#             if module_name in sys.modules:
#                 importlib.reload(sys.modules[module_name])
#                 print(f"Reloaded: {module_name}")
#             else:
#                 print(
#                     f"Skipped reloading {module_name}: not found in sys.modules (might have been removed)."
#                 )
#         except Exception as e:
#             print(f"Failed to reload {module_name}: {e}")

#     # After reloading, clear out the existing references to old classes
#     # from the global scope of this __init__.py, so new ones can be imported.
#     # This is important to prevent stale references.
#     from inspect import isclass, isfunction

#     current_module_members = locals().copy()
#     for name, obj in current_module_members.items():
#         if name in (
#             "__init__",
#             "__main__",
#             "__file__",
#             "__name__",
#             "__package__",
#             "__spec__",
#             "bpy",
#             "sys",
#             "importlib",
#             "getmembers",
#             "isclass",
#             "isfunction",
#             "addon_name",
#             "addon_modules_to_reload",
#         ):  # Add any new local variables here
#             continue

#         if isclass(obj) or isfunction(obj):
#             # Attempt to delete the old reference
#             try:
#                 del locals()[name]
#             except KeyError:
#                 pass


from .operators import Splatter_OT_Generate_Room, Splatter_OT_Segment_Scene
from .ui import Splatter_PT_Main_Panel

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
    Splatter_OT_Segment_Scene,
    Splatter_OT_Generate_Room,
    Splatter_PT_Main_Panel,
)


def register():
    print(f"Registering {bl_info.get('name')} version {bl_info.get('version')}")
    for cls in classesToRegister:
        bpy.utils.register_class(cls)

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

    # Example: Remove addon preferences
    # bpy.utils.unregister_class(MyAddonPreferences)

    # Example: Delete custom properties
    # del bpy.types.Scene.my_addon_property


if __name__ == "__main__":
    register()
