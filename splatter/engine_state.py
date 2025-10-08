# Engine State Management
# This module contains global state variables for tracking the external C++ engine
#
# State Categories:
# - Process State (engine.py): Raw subprocess lifecycle, direct communication
# - Sync Bridge State (engine_state.py): High-level connection status, sync metadata, operation queues

# Track the expected engine state for each group (what the engine thinks attributes should be)
# Key: group name (str), Value: dict of {attr_name: value}
# Only includes groups that have been processed by align_to_axes
_engine_expected_state = {}

# Cache whether the engine has any groups stored (once true, stays true since groups are never deleted)
_engine_has_groups_cached = False

# Cache the current parent groups dictionary (group_name -> list of parent objects)
_engine_parent_groups = {}
_engine_license_match = True
_engine_license_mode = "UNKNOWN"


def get_engine_has_groups_cached() -> bool:
    """Get the cached value of whether the engine has groups stored."""
    return _engine_has_groups_cached


def set_engine_has_groups_cached(has_groups: bool) -> None:
    """Set the cached value of whether the engine has groups stored.
    
    Once set to True, it stays True since groups are never deleted.
    """
    global _engine_has_groups_cached
    if has_groups:
        _engine_has_groups_cached = True


def get_engine_parent_groups() -> dict:
    """Get the cached parent groups dictionary."""
    return _engine_parent_groups


def set_engine_parent_groups(parent_groups: dict) -> None:
    """Set the cached parent groups dictionary.
    
    This should be called after classification to store the current group structure.
    Merges with existing groups, overwriting old entries by the same name and adding new ones.
    """
    global _engine_parent_groups
    _engine_parent_groups.update(parent_groups)


def set_engine_license_status(match: bool, engine_mode: str) -> None:
    """Record the engine license compatibility information."""
    global _engine_license_match, _engine_license_mode
    _engine_license_match = bool(match)
    _engine_license_mode = engine_mode


def get_engine_license_status() -> tuple[bool, str]:
    """Retrieve the last known engine license compatibility information."""
    return _engine_license_match, _engine_license_mode

