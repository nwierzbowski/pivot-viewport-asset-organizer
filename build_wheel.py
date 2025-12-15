#!/usr/bin/env python3
# Copyright (C) 2025 Nicholas Wierzbowski / Elbo Studio
# This file is part of the Pivot Bridge for Blender.
#
# Build script for creating platform-specific wheels from pre-compiled .so/.pyd files.
# This script is designed to be run AFTER cmake has compiled the Cython modules.
#
# Usage:
#   python build_wheel.py [--output-dir DIR]
#
# The script will:
#   1. Ensure pivot_lib has compiled modules
#   2. Build a wheel using the Python build module
#   3. Output to pivot/wheels/

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_extension_suffix():
    """Get the file extension for compiled modules."""
    if platform.system() == "Windows":
        return ".pyd"
    return ".so"


def main():
    parser = argparse.ArgumentParser(description="Build pivot_lib wheel from pre-compiled modules")
    parser.add_argument("--output-dir", "-o", default=None, help="Output directory for wheel (default: pivot/wheels)")
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    pkg_dir = script_dir / "pivot_lib"
    
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = script_dir / "pivot" / "wheels"
    
    # Check for compiled modules
    ext_suffix = get_extension_suffix()
    modules = list(pkg_dir.glob(f"*{ext_suffix}"))
    
    if not modules:
        print(f"Error: No compiled modules found in {pkg_dir}")
        print("Make sure to build with cmake first: ninja -C build-pro")
        sys.exit(1)
    
    print(f"Found {len(modules)} compiled modules:")
    for mod in modules:
        print(f"  {mod.name}")
    
    # Clean up previous builds
    for cleanup_dir in ["build", "pivot_lib.egg-info"]:
        cleanup_path = pkg_dir / cleanup_dir
        if cleanup_path.exists():
            shutil.rmtree(cleanup_path)
    
    # Build the wheel
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nBuilding wheel...")
    
    cmd = [
        sys.executable, "-m", "build",
        "--wheel",
        "--outdir", str(output_dir),
    ]
    
    result = subprocess.run(cmd, cwd=pkg_dir)
    
    if result.returncode != 0:
        print("Error: Wheel build failed")
        sys.exit(1)
    
    print(f"\nWheel built successfully in {output_dir}")
    
    # List the wheel(s)
    for whl in output_dir.glob("pivot_lib-*.whl"):
        print(f"  {whl.name}")


if __name__ == "__main__":
    main()
