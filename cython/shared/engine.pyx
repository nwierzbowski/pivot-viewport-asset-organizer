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

"""Pivot Engine Management Module

This module provides a unified interface for managing the C++ pivot engine subprocess.

Responsibilities:
- Process lifecycle management (start/stop subprocess)
- Direct communication interface (JSON commands)
- Low-level process state (is_running, PID, etc.)
"""

import os
import subprocess
import atexit
import json
import platform
import builtins
import sys
from typing import Dict, Any, Optional

from pivot_lib import engine_state

# Command IDs for engine communication
cdef int COMMAND_SET_SURFACE_TYPES = 4
cdef int COMMAND_DROP_GROUPS = 5
cdef int COMMAND_CLASSIFY_GROUPS = 1
cdef int COMMAND_CLASSIFY_OBJECTS = 1
cdef int COMMAND_GET_GROUP_SURFACE_TYPES = 2


def get_engine_binary_path() -> str:
    """Get the path to the correct engine binary for this platform/architecture.
    
    Returns:
        str: Path to the pivot_engine executable
    """
    bin_dir = None
    
    # For Blender extensions, find the pivot extension directory
    # The extension is installed as bl_ext.<repo>.<extension_name>.pivot
    try:
        # Look for the main pivot module - could be named various ways
        pivot_module_names = [
            'bl_ext.vscode_development.pivot',  # VS Code development
            'bl_ext.user_default.pivot',        # User installed
            'pivot',                            # Direct import
        ]
        
        for mod_name in pivot_module_names:
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                if hasattr(mod, '__file__') and mod.__file__:
                    pivot_dir = os.path.dirname(mod.__file__)
                    potential_bin = os.path.join(pivot_dir, 'bin')
                    if os.path.exists(potential_bin):
                        bin_dir = potential_bin
                        break
        
        # Also search for any module ending with .pivot that has a bin directory
        if bin_dir is None:
            for mod_name, mod in sys.modules.items():
                if mod_name.endswith('.pivot') and hasattr(mod, '__file__') and mod.__file__:
                    pivot_dir = os.path.dirname(mod.__file__)
                    potential_bin = os.path.join(pivot_dir, 'bin')
                    if os.path.exists(potential_bin):
                        bin_dir = potential_bin
                        break
    except Exception as e:
        print(f"[Pivot] Error finding pivot module path: {e}")
    
    # Fallback: search sys.path for pivot/bin
    if bin_dir is None:
        for path in sys.path:
            potential_bin = os.path.join(path, 'pivot', 'bin')
            if os.path.exists(potential_bin):
                bin_dir = potential_bin
                break
            # Also check if path itself is the pivot directory
            if path.endswith('pivot'):
                potential_bin = os.path.join(path, 'bin')
                if os.path.exists(potential_bin):
                    bin_dir = potential_bin
                    break
    
    # Last resort for development: navigate from blender-bridge
    if bin_dir is None:
        module_dir = os.path.dirname(__file__) if '__file__' in dir() else os.getcwd()
        # Try various paths relative to where pivot_lib might be
        candidates = [
            os.path.join(module_dir, '..', 'pivot', 'bin'),  # site-packages layout
            os.path.join(module_dir, '..', '..', 'pivot', 'bin'),  # nested
            os.path.join(module_dir, '..', '..', 'blender-bridge', 'pivot', 'bin'),  # dev layout
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                bin_dir = candidate
                break
        else:
            bin_dir = candidates[0]  # Use first as fallback even if doesn't exist
    
    # Detect OS and architecture
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Map architecture names
    if machine in ('x86_64', 'amd64'):
        arch = 'x86-64'
    elif machine in ('aarch64', 'arm64'):
        arch = 'arm64'
    else:
        arch = machine
    
    # Determine binary name
    if system == 'windows':
        exe_name = 'pivot_engine.exe'
    else:
        exe_name = 'pivot_engine'
    
    # Platform identifier for directories
    platform_id = f'{system}-{arch}'
    
    # Try platform-specific subdirectory first
    platform_dir = os.path.join(bin_dir, platform_id)
    platform_binary = os.path.join(platform_dir, exe_name)
    if os.path.exists(platform_binary):
        return platform_binary
    
    # Fallback to root bin directory (legacy structure)
    fallback_binary = os.path.join(bin_dir, exe_name)
    return fallback_binary


def get_platform_id() -> str:
    """Get platform identifier for module loading (e.g., 'linux-x86-64', 'macos-arm64').
    
    Returns:
        str: Platform identifier string
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Map architecture names
    if machine in ('x86_64', 'amd64'):
        arch = 'x86-64'
    elif machine in ('aarch64', 'arm64'):
        arch = 'arm64'
    else:
        arch = machine
    
    return f'{system}-{arch}'


cdef class PivotEngine:
    """Unified interface for the C++ pivot engine subprocess."""

    cdef object _process
    cdef bint _is_running

    def __init__(self):
        self._process = None
        self._is_running = False

    def start(self) -> bint:
        """Start the pivot engine executable.

        Returns:
            bool: True if started successfully, False otherwise
        """
        if self._is_running:
            print("Pivot engine is already running")
            return True

        try:
            # Get the path to the executable for this platform/architecture
            engine_path = get_engine_binary_path()
            print(f"Engine path: {engine_path}")

            # Check if executable exists
            if not os.path.exists(engine_path):
                print(f"Warning: Engine executable not found at {engine_path}")
                return False

            print(f"Starting pivot engine: {engine_path}")

            # Start the engine process
            self._process = subprocess.Popen(
                [engine_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,  # Inherit stderr to show in Blender console
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )

            self._is_running = True
            print("Pivot engine started successfully")
            return True

        except Exception as e:
            print(f"Failed to start pivot engine: {e}")
            self._process = None
            self._is_running = False
            return False

    def stop(self) -> None:
        """Stop the pivot engine executable."""
        if not self._is_running or self._process is None:
            return

        try:
            print("Stopping pivot engine...")

            # Send quit command to the engine
            if self._process.poll() is None:  # Process is still running
                try:
                    self._process.stdin.write("__quit__\n")
                    self._process.stdin.flush()

                    # Wait a bit for graceful shutdown
                    self._process.wait(timeout=2.0)
                except (subprocess.TimeoutExpired, BrokenPipeError):
                    # Force kill if graceful shutdown fails
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait()

            print("Pivot engine stopped")
            self._process = None
            self._is_running = False

        except Exception as e:
            print(f"Error stopping pivot engine: {e}")
            if self._process:
                try:
                    self._process.kill()
                except:
                    pass
            self._process = None
            self._is_running = False

    def is_running(self) -> bint:
        """Check if the engine is currently running."""
        return self._is_running and self._process is not None and self._process.poll() is None

    def send_command(self, dict command_dict) -> dict:
        """Send a command to the engine and get the final response."""
        if not self.is_running():
            raise RuntimeError("Engine process not started or has terminated. Make sure the addon is properly registered.")

        try:
            # Send command as JSON
            command_json = json.dumps(command_dict) + "\n"
            self._process.stdin.write(command_json)
            self._process.stdin.flush()

            # Read responses until we get the final one (with "ok")
            while True:
                response_line = self._process.stdout.readline().strip()
                if not response_line:
                    raise RuntimeError("Engine process terminated unexpectedly")

                response = json.loads(response_line)
                if "ok" in response:
                    return response

        except Exception as e:
            raise RuntimeError(f"Communication error: {e}")

    def send_command_async(self, dict command_dict) -> None:
        """Send a command to the engine without waiting for response."""
        if not self.is_running():
            raise RuntimeError("Engine process not started or has terminated. Make sure the addon is properly registered.")

        try:
            command_json = json.dumps(command_dict) + "\n"
            self._process.stdin.write(command_json)
            self._process.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"Communication error: {e}")

    def wait_for_response(self, int expected_id) -> dict:
        """Wait for a response with the specified ID."""
        if not self.is_running():
            raise RuntimeError("Engine process not started or has terminated. Make sure the addon is properly registered.")

        try:
            while True:
                response_line = self._process.stdout.readline().strip()
                if not response_line:
                    raise RuntimeError("Engine process terminated unexpectedly")

                response = json.loads(response_line)
                if response.get("id") == expected_id:
                    return response

        except Exception as e:
            raise RuntimeError(f"Communication error: {e}")

    def send_group_classifications(self, dict group_surface_map) -> bint:
        """Send a batch classification update to the engine."""
        if not group_surface_map:
            return True

        if not self.is_running():
            return False

        cdef list payload = []
        for name, value in group_surface_map.items():
            try:
                surface_int = int(value)
            except (TypeError, ValueError):
                continue
            payload.append({"group_name": name, "surface_type": surface_int})

        if not payload:
            return True

        try:
            command = {
                "id": COMMAND_SET_SURFACE_TYPES,
                "op": "set_surface_types",
                "classifications": payload
            }
            response = self.send_command(command)
            if not response.get("ok", False):
                error = response.get("error", "Unknown error")
                print(f"Failed to update group classifications: {error}")
                return False
            return True
        except Exception as exc:
            print(f"Error sending group classifications: {exc}")
            return False

    def drop_groups(self, list group_names) -> int:
        """Drop groups from the engine cache."""
        if not group_names:
            return 0

        if not self.is_running():
            return -1

        try:
            command = {
                "id": COMMAND_DROP_GROUPS,
                "op": "drop_groups",
                "group_names": group_names
            }
            response = self.send_command(command)
            if not response.get("ok", False):
                error = response.get("error", "Unknown error")
                print(f"Failed to drop groups from engine: {error}")
                return -1
            dropped_count = response.get("dropped_count", 0)
            return dropped_count
        except Exception as exc:
            print(f"Error dropping groups from engine: {exc}")
            return -1

    def build_standardize_groups_command(self, str verts_shm_name, str edges_shm_name, 
                                     str rotations_shm_name, str scales_shm_name, 
                                     str offsets_shm_name, list vert_counts, 
                                     list edge_counts, list object_counts, 
                                     list group_names, list surface_contexts) -> dict:
        """Build a standardize_groups command for the engine (Pro edition)."""
        return {
            "id": COMMAND_CLASSIFY_GROUPS,
            "op": "standardize_groups",
            "shm_verts": verts_shm_name,
            "shm_edges": edges_shm_name,
            "shm_rotations": rotations_shm_name,
            "shm_scales": scales_shm_name,
            "shm_offsets": offsets_shm_name,
            "vert_counts": vert_counts,
            "edge_counts": edge_counts,
            "object_counts": object_counts,
            "group_names": group_names,
            "surface_contexts": surface_contexts,
        }

    def build_standardize_synced_groups_command(self, list group_names, list surface_contexts) -> dict:
        """Build a command to reclassify already-synced groups without uploading mesh data."""
        return {
            "id": COMMAND_CLASSIFY_GROUPS,
            "op": "standardize_synced_groups",
            "group_names": group_names,
            "surface_contexts": surface_contexts
        }

    def build_standardize_objects_command(self, str verts_shm_name, str edges_shm_name,
                                      str rotations_shm_name, str scales_shm_name,
                                      str offsets_shm_name, list vert_counts,
                                      list edge_counts, list object_names, list surface_contexts) -> dict:
        """Build a standardize_objects command for the engine."""
        return {
            "id": COMMAND_CLASSIFY_OBJECTS,
            "op": "standardize_objects",
            "shm_verts": verts_shm_name,
            "shm_edges": edges_shm_name,
            "shm_rotations": rotations_shm_name,
            "shm_scales": scales_shm_name,
            "shm_offsets": offsets_shm_name,
            "vert_counts": vert_counts,
            "edge_counts": edge_counts,
            "object_names": object_names,
            "surface_contexts": surface_contexts
        }

    def build_get_surface_types_command(self) -> dict:
        """Build a get_surface_types command for the engine."""
        return {
            "id": COMMAND_GET_GROUP_SURFACE_TYPES,
            "op": "get_surface_types"
        }


# Global engine instance stored on builtins to persist across reloads
cdef PivotEngine _engine_instance

_temp_instance = getattr(builtins, '_pivot_engine_instance', None)
if _temp_instance is None:
    _engine_instance = PivotEngine()
    builtins._pivot_engine_instance = _engine_instance
else:
    _engine_instance = _temp_instance
    if _engine_instance.is_running():
        _engine_instance.stop()


def start_engine() -> bint:
    """Start the pivot engine (convenience function)."""
    return _engine_instance.start()


def stop_engine() -> None:
    """Stop the pivot engine (convenience function)."""
    _engine_instance.stop()


def get_engine_communicator() -> PivotEngine:
    """Get the engine instance for communication."""
    if not _engine_instance.is_running():
        started = _engine_instance.start()
        if not started:
            raise RuntimeError("Engine process not started. Make sure the addon is properly registered.")
    return _engine_instance


def get_engine_process():
    """Get the current engine process (for backward compatibility)."""
    return _engine_instance._process


def sync_license_mode() -> str:
    """Retrieve the compiled edition from the engine."""
    engine_comm = get_engine_communicator()
    payload = {
        "id": 0,
        "op": "sync_license",
    }
    response = engine_comm.send_command(payload)
    engine_mode = str(response.get("engine_edition", "UNKNOWN")).upper()
    return engine_mode


# Register cleanup function to run on Python exit
atexit.register(stop_engine)
