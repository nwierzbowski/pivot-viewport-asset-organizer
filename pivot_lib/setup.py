#!/usr/bin/env python3
# Copyright (C) 2025 Nicholas Wierzbowski / Elbo Studio
# This file is part of the Pivot Bridge for Blender.
#
# setup.py for building pivot_lib wheel with pre-compiled Cython extensions.
# This file is only used for wheel building, not for installation.

import os
import platform
import shutil
from pathlib import Path
from setuptools import setup, Extension
from setuptools.dist import Distribution


def get_extension_suffix():
    """Get the file extension for compiled modules."""
    if platform.system() == "Windows":
        return ".pyd"
    return ".so"


class BinaryDistribution(Distribution):
    """Distribution that always builds platform-specific wheels."""
    def has_ext_modules(self):
        return True


def get_extensions():
    """Find all pre-compiled extension modules."""
    pkg_dir = Path(__file__).parent / "pivot_lib"
    ext_suffix = get_extension_suffix()
    
    extensions = []
    for ext_file in pkg_dir.glob(f"*{ext_suffix}"):
        # Create a dummy extension that setuptools will include
        mod_name = ext_file.stem
        extensions.append(Extension(f"pivot_lib.{mod_name}", sources=[]))
    
    return extensions


def get_package_data():
    """Get all pre-compiled modules to include in the package."""
    pkg_dir = Path(__file__).parent / "pivot_lib"
    ext_suffix = get_extension_suffix()
    
    files = [f.name for f in pkg_dir.glob(f"*{ext_suffix}")]
    return {"pivot_lib": files}


setup(
    name="pivot_lib",
    version="1.0.0",
    description="Cython extension modules for Pivot Blender addon",
    author="Nicholas Wierzbowski",
    author_email="nicholas.wierzbowski@elbo.studio",
    url="https://www.elbo.studio",
    license="GPL-3.0-or-later",
    packages=["pivot_lib"],
    package_data=get_package_data(),
    include_package_data=True,
    python_requires=">=3.11",
    distclass=BinaryDistribution,
    zip_safe=False,
)
