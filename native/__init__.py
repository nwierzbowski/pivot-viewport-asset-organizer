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

"""Pivot Cython extension modules.

This package provides compiled Cython extension modules for Pivot.
When installed as a wheel, all modules are available directly:

    from pivot_lib import classification
    from pivot_lib import collection_manager
    from pivot_lib import edition_utils
    from elbo_sdk import engine
    from pivot_lib import engine_state
    from pivot_lib import group_manager
    from pivot_lib import selection_utils
    from pivot_lib import shm_utils
    from elbo_sdk import shm_bridge
    from pivot_lib import standardize
    from pivot_lib import surface_manager
"""

__version__ = "1.0.0"

__all__ = [
    "classification",
    "collection_manager",
    "edition_utils",
    "engine",  # shim -> elbo_sdk.engine
    "engine_state",
    "group_manager",
    "selection_utils",
    "shm_utils",
    "standardize",
    "surface_manager",
]
