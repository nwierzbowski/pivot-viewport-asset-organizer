#!/usr/bin/env python3
# Copyright (C) 2025 Nicholas Wierzbowski / Elbo Studio
# This file is part of the Pivot Bridge for Blender.
#
# Minimal setup.py for platform-specific wheels with pre-compiled Cython extensions.

import os
import platform
import shutil
from pathlib import Path
from setuptools import setup, Extension
from setuptools.dist import Distribution
from setuptools.command.build_ext import build_ext


class BinaryDistribution(Distribution):
    """Distribution that always builds platform-specific wheels."""
    def has_ext_modules(self):
        return True


class PrecompiledBuildExt(build_ext):
    def build_extension(self, ext):
        if not ext.sources:
            # Precompiled, copy the .so to the target
            mod_name = ext.name.split('.')[-1]
            src = Path(mod_name).with_suffix('.so')
            if platform.system() == "Windows":
                src = src.with_suffix('.pyd')
            target = self.get_ext_fullpath(ext.name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target)
            print(f"Copied {src} to {target}")
        else:
            super().build_extension(ext)


def get_extensions():
    """Find all pre-compiled extension modules."""
    pkg_dir = Path(__file__).parent
    ext_suffix = ".pyd" if platform.system() == "Windows" else ".so"
    
    extensions = []
    for ext_file in pkg_dir.glob(f"*{ext_suffix}"):
        # Create a dummy extension that setuptools will include
        mod_name = ext_file.stem
        extensions.append(Extension(f"pivot_lib.{mod_name}", sources=[]))
    
    return extensions


setup(
    distclass=BinaryDistribution,
    ext_modules=get_extensions(),
    cmdclass={'build_ext': PrecompiledBuildExt},
)
