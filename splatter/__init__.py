import bpy
import os
import subprocess
import atexit

from .classes import ObjectAttributes
from bpy.props import PointerProperty

from .operators import (
    Splatter_OT_Align_To_Axes,
    Splatter_OT_Classify_Base,
    Splatter_OT_Classify_Object,
    Splatter_OT_Selection_To_Seating,
    Splatter_OT_Selection_To_Surfaces,
    Splatter_OT_Classify_Faces,
    Splatter_OT_Generate_Base,
    Splatter_OT_Segment_Scene,
    Splatter_OT_Select_Surfaces,
    Splatter_OT_Select_Seating,
)
from .ui import Splatter_PT_Main_Panel

# Global variable to track the engine process
_engine_process = None

def _read_engine_output():
    """Debug function to read and print engine output."""
    if _engine_process is None:
        print("No engine process running")
        return
    
    # Read any available output
    if _engine_process.stdout:
        try:
            while True:
                line = _engine_process.stdout.readline()
                if not line:
                    break
                print(f"[ENGINE STDOUT] {line.strip()}")
        except:
            pass
    
    if _engine_process.stderr:
        try:
            while True:
                line = _engine_process.stderr.readline()
                if not line:
                    break
                print(f"[ENGINE STDERR] {line.strip()}")
        except:
            pass


def _start_engine():
    """Start the splatter engine executable."""
    global _engine_process

    if _engine_process is not None:
        print("Splatter engine is already running")
        return

    try:
        # Get the path to the executable relative to this file
        addon_dir = os.path.dirname(__file__)
        engine_path = os.path.join(addon_dir, 'bin', 'splatter_engine')

        # Check if executable exists
        if not os.path.exists(engine_path):
            print(f"Warning: Engine executable not found at {engine_path}")
            return

        print(f"Starting splatter engine: {engine_path}")

        # Start the engine process
        _engine_process = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        print("Splatter engine started successfully")

    except Exception as e:
        print(f"Failed to start splatter engine: {e}")
        _engine_process = None


def _stop_engine():
    """Stop the splatter engine executable."""
    global _engine_process

    if _engine_process is None:
        return

    try:
        print("Stopping splatter engine...")

        # Send quit command to the engine
        if _engine_process.poll() is None:  # Process is still running
            try:
                _engine_process.stdin.write("__quit__\n")
                _engine_process.stdin.flush()

                # Wait a bit for graceful shutdown
                _engine_process.wait(timeout=2.0)
            except (subprocess.TimeoutExpired, BrokenPipeError):
                # Force kill if graceful shutdown fails
                _engine_process.terminate()
                try:
                    _engine_process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    _engine_process.kill()
                    _engine_process.wait()

        print("Splatter engine stopped")
        _engine_process = None

    except Exception as e:
        print(f"Error stopping splatter engine: {e}")
        if _engine_process:
            try:
                _engine_process.kill()
            except:
                pass
        _engine_process = None





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
    ObjectAttributes,
    Splatter_OT_Segment_Scene,
    Splatter_OT_Generate_Base,
    Splatter_OT_Classify_Base,
    Splatter_PT_Main_Panel,
    Splatter_OT_Classify_Faces,
    Splatter_OT_Select_Surfaces,
    Splatter_OT_Selection_To_Surfaces,
    Splatter_OT_Select_Seating,
    Splatter_OT_Selection_To_Seating,
    Splatter_OT_Classify_Object,
    Splatter_OT_Align_To_Axes,
)


def register():
    print(f"Registering {bl_info.get('name')} version {bl_info.get('version')}")
    for cls in classesToRegister:
        bpy.utils.register_class(cls)
    bpy.types.Object.classification = PointerProperty(type=ObjectAttributes)

    # Start the splatter engine
    _start_engine()

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

    del bpy.types.Object.classification

    # Stop the splatter engine
    _stop_engine()

    # Example: Remove addon preferences
    # bpy.utils.unregister_class(MyAddonPreferences)

    # Example: Delete custom properties
    # del bpy.types.Scene.my_addon_property


if __name__ == "__main__":
    register()

# Register cleanup function to run on Python exit
atexit.register(_stop_engine)
