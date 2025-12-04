"""Platform-aware loader for Pivot Cython modules.

This package exposes compiled extension modules located in platform-specific
subdirectories (e.g. ``lib/linux-x86-64``) while presenting a stable import
surface such as ``from pivot.lib import classify_object``.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
import types
from types import ModuleType
from typing import Dict

__all__ = [
    "classification",
    "edition_utils",
    "group_manager",
    "selection_utils",
    "shm_utils",
    "standardize",
]

# Cache of already imported extension modules keyed by attribute name
_loaded_modules: Dict[str, ModuleType] = {}


def _determine_platform_id() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "x86-64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        arch = machine
    return f"{system}-{arch}"


def _ensure_platform_path() -> None:
    """Ensure the platform-specific directory is available on ``sys.path``."""
    base_dir = os.path.dirname(__file__)
    platform_dir = os.path.join(base_dir, _determine_platform_id())

    # Prefer the platform-specific directory when present
    candidates = [platform_dir, base_dir]
    for candidate in candidates:
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)


_ensure_platform_path()


def _load_module(name: str) -> ModuleType:
    # Load .so file directly using spec_from_file_location to avoid issues with hyphens in directory names
    platform_id = _determine_platform_id()
    base_dir = os.path.dirname(__file__)
    platform_dir = os.path.join(base_dir, platform_id)
    
    # Try .so first (Linux/macOS), then .pyd (Windows)
    so_path = os.path.join(platform_dir, f"{name}.so")
    pyd_path = os.path.join(platform_dir, f"{name}.pyd")
    
    module_path = None
    if os.path.exists(so_path):
        module_path = so_path
    elif os.path.exists(pyd_path):
        module_path = pyd_path
    
    if not module_path:
        raise ImportError(f"Cannot find compiled module '{name}' for platform '{platform_id}'")
    
    # Create module spec from file location
    full_name = f"{__name__}.{name}"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create module spec for '{name}'")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    
    # Expose module under attribute
    _loaded_modules[name] = module
    globals()[name] = module
    return module


def __getattr__(name: str) -> ModuleType:
    if name not in __all__:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    return _loaded_modules.get(name) or _load_module(name)


def __dir__() -> list[str]:
    return sorted(list(__all__) + [key for key in globals().keys() if not key.startswith("_")])
