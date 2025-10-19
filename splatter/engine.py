"""
Splatter Engine Management Module

This module provides a unified interface for managing the C++ splatter engine subprocess.

Responsibilities:
- Process lifecycle management (start/stop subprocess)
- Direct communication interface (JSON commands)
- Low-level process state (is_running, PID, etc.)

Note: High-level sync bridge state (connection status, expected state, etc.) 
is managed in engine_state.py for separation of concerns.
"""

import os
import subprocess
import atexit
import json
import select
from typing import Dict, Any, Optional, Tuple

# Command IDs for engine communication
COMMAND_SET_GROUP_CLASSIFICATIONS = 4
COMMAND_DROP_GROUPS = 5


class SplatterEngine:
    """Unified interface for the C++ splatter engine subprocess.

    This class encapsulates all engine-related functionality:
    - Process lifecycle management (start/stop)
    - Communication interface
    - Error handling and cleanup
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._is_running = False

    def start(self) -> bool:
        """Start the splatter engine executable.

        Returns:
            bool: True if started successfully, False otherwise
        """
        if self._is_running:
            print("Splatter engine is already running")
            return True

        try:
            # Get the path to the executable relative to this file
            addon_dir = os.path.dirname(os.path.dirname(__file__))  # Go up from splatter/
            # Resolve engine binary name based on OS
            engine_name = 'splatter_engine.exe' if os.name == 'nt' else 'splatter_engine'
            engine_path = os.path.join(addon_dir, 'splatter', 'bin', engine_name)
            print(f"Engine path: {engine_path}")

            # Check if executable exists
            if not os.path.exists(engine_path):
                print(f"Warning: Engine executable not found at {engine_path}")
                return False

            print(f"Starting splatter engine: {engine_path}")

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
            print("Splatter engine started successfully")
            return True

        except Exception as e:
            print(f"Failed to start splatter engine: {e}")
            self._process = None
            self._is_running = False
            return False

    def stop(self) -> None:
        """Stop the splatter engine executable."""
        if not self._is_running or self._process is None:
            return

        try:
            print("Stopping splatter engine...")

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

            print("Splatter engine stopped")
            self._process = None
            self._is_running = False

        except Exception as e:
            print(f"Error stopping splatter engine: {e}")
            if self._process:
                try:
                    self._process.kill()
                except:
                    pass
            self._process = None
            self._is_running = False

    def is_running(self) -> bool:
        """Check if the engine is currently running."""
        return self._is_running and self._process is not None and self._process.poll() is None

    def send_command(self, command_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the engine and get the final response.

        Args:
            command_dict: Command to send as a dictionary

        Returns:
            Dict containing the engine's final response

        Raises:
            RuntimeError: If engine is not running or communication fails
        """
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

    def send_command_async(self, command_dict: Dict[str, Any]) -> None:
        """Send a command to the engine without waiting for response.

        Args:
            command_dict: Command to send as a dictionary

        Raises:
            RuntimeError: If engine is not running or communication fails
        """
        if not self.is_running():
            raise RuntimeError("Engine process not started or has terminated. Make sure the addon is properly registered.")

        try:
            # Send command as JSON
            command_json = json.dumps(command_dict) + "\n"
            self._process.stdin.write(command_json)
            self._process.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"Communication error: {e}")

    def wait_for_response(self, expected_id: int) -> Dict[str, Any]:
        """Wait for a response with the specified ID.

        Args:
            expected_id: The ID of the response to wait for

        Returns:
            Dict containing the engine's response

        Raises:
            RuntimeError: If engine is not running or communication fails
        """
        if not self.is_running():
            raise RuntimeError("Engine process not started or has terminated. Make sure the addon is properly registered.")

        try:
            # Read responses until we get the one with the expected ID
            while True:
                response_line = self._process.stdout.readline().strip()
                if not response_line:
                    raise RuntimeError("Engine process terminated unexpectedly")

                response = json.loads(response_line)
                if response.get("id") == expected_id:
                    return response

        except Exception as e:
            raise RuntimeError(f"Communication error: {e}")

    def send_group_classifications(self, group_surface_map: Dict[str, Any]) -> bool:
        """Send a batch classification update to the engine."""
        if not group_surface_map:
            return True

        if not self.is_running():
            return False

        payload = []
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
                "id": COMMAND_SET_GROUP_CLASSIFICATIONS,
                "op": "set_group_classifications",
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

    def drop_groups(self, group_names: list[str]) -> int:
        """Drop groups from the engine cache.

        Args:
            group_names: List of group names to drop from the cache

        Returns:
            int: Number of groups actually dropped, or -1 on error
        """
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


# Global engine instance
_engine_instance = SplatterEngine()


def start_engine() -> bool:
    """Start the splatter engine (convenience function)."""
    return _engine_instance.start()


def stop_engine() -> None:
    """Stop the splatter engine (convenience function)."""
    _engine_instance.stop()


def get_engine_communicator() -> SplatterEngine:
    """Get the engine instance for communication."""
    if not _engine_instance.is_running():
        raise RuntimeError("Engine process not started. Make sure the addon is properly registered.")
    return _engine_instance


def get_engine_process():
    """Get the current engine process (for backward compatibility)."""
    return _engine_instance._process


def sync_license_mode() -> str:
    """Retrieve the compiled edition from the engine.

    Returns:
        The engine_mode is the
        edition compiled into the engine binary ("PRO", "STANDARD", or "UNKNOWN").

    Raises:
        RuntimeError: If communication with the engine fails.
    """

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
