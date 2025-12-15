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

"""Engine State Management

Hosts global state that describes what the external C++ engine currently 
believes about the scene. Keeping this module slim makes it easy to reason 
about how Blender-side edits diverge from the engine.
"""

from typing import Dict, Iterable, Mapping, Set

cdef str _engine_license_mode = "UNKNOWN"

# Membership snapshot returned by the engine: group name -> set of object names.
cdef dict _group_membership_snapshot = {}

# Flag to indicate if classification is in progress
cdef bint _is_performing_classification = False


# ---------------------------------------------------------------------------
# License helpers
# ---------------------------------------------------------------------------

def set_engine_license_status(str engine_mode) -> None:
    """Record the engine license compatibility information."""
    global _engine_license_mode
    _engine_license_mode = engine_mode


def get_engine_license_status() -> str:
    """Return the last known engine license mode."""
    return _engine_license_mode


# ---------------------------------------------------------------------------
# Classification flag helpers
# ---------------------------------------------------------------------------

def set_performing_classification(bint value) -> None:
    """Set whether classification is currently in progress."""
    global _is_performing_classification
    _is_performing_classification = value


def is_performing_classification() -> bint:
    """Check if classification is currently in progress."""
    return _is_performing_classification


# ---------------------------------------------------------------------------
# Membership snapshot APIs
# ---------------------------------------------------------------------------

def update_group_membership_snapshot(snapshot: Mapping[str, Iterable[str]], *, bint replace = False) -> None:
    """Persist the engine-reported membership snapshot.

    Args:
        snapshot: Mapping of group name -> iterable of object names the engine used.
        replace:  When True, discard all prior snapshot data before applying updates.
    """
    global _group_membership_snapshot

    if replace:
        drop_groups_from_snapshot(list(_group_membership_snapshot.keys()))
        _group_membership_snapshot.clear()

    for name, members in snapshot.items():
        member_set = set(members)
        _group_membership_snapshot[name] = member_set


def build_group_membership_snapshot(list full_groups, list group_names) -> dict:
    """Create a mapping of group names to object names for state tracking.
    
    Args:
        full_groups: List of object groups
        group_names: Parallel list of group names
        
    Returns:
        Dict mapping group name -> list of object names
    """
    cdef dict snapshot = {}
    cdef int idx
    cdef object group
    cdef str group_name
    
    for idx, group in enumerate(full_groups):
        group_name = group_names[idx]
        if group_name is not None:
            snapshot[group_name] = [obj.name for obj in group if obj is not None]
    return snapshot


def get_group_membership_snapshot() -> Dict[str, Set[str]]:
    """Return a deep copy of the engine membership snapshot."""
    return {name: set(members) for name, members in _group_membership_snapshot.items()}


def drop_groups_from_snapshot(group_names: Iterable[str]) -> None:
    """Remove groups that are no longer managed by Pivot."""
    for name in group_names:
        _group_membership_snapshot.pop(name, None)
