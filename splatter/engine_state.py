# Engine State Management
# ------------------------
# Hosts tiny pieces of global state that describe what the external C++
# engine currently believes about the scene. Keeping this module slim makes
# it easy to reason about how Blender-side edits diverge from the engine.

from typing import Dict, Iterable, Mapping, Set

_engine_license_mode = "UNKNOWN"

# Membership snapshot returned by the engine: group name -> set of object names.
_group_membership_snapshot: Dict[str, Set[str]] = {}

# Groups that Blender has marked dirty since the last successful engine sync.
_unsynced_groups: Set[str] = set()


# ---------------------------------------------------------------------------
# License helpers
# ---------------------------------------------------------------------------

def set_engine_license_status(engine_mode: str) -> None:
    """Record the engine license compatibility information."""
    global _engine_license_mode
    _engine_license_mode = engine_mode


def get_engine_license_status() -> str:
    """Return the last known engine license mode."""
    return _engine_license_mode


# ---------------------------------------------------------------------------
# Membership snapshot APIs
# ---------------------------------------------------------------------------

def update_group_membership_snapshot(snapshot: Mapping[str, Iterable[str]], *, replace: bool = False) -> None:
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
        _unsynced_groups.discard(name)


def build_group_membership_snapshot(full_groups, group_names):
    """Create a mapping of group names to object names for state tracking.
    
    Args:
        full_groups: List of object groups
        group_names: Parallel list of group names
        
    Returns:
        Dict mapping group name -> list of object names
    """
    snapshot = {}
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
        _unsynced_groups.discard(name)


# ---------------------------------------------------------------------------
# Unsynced bookkeeping
# ---------------------------------------------------------------------------

def flag_group_unsynced(group_name: str) -> None:
    """Remember that a group needs a round-trip to the engine."""
    if group_name:
        _unsynced_groups.add(group_name)


def clear_group_unsynced(group_name: str) -> None:
    """Mark a group as freshly synced with the engine."""
    _unsynced_groups.discard(group_name)


def get_unsynced_groups() -> Set[str]:
    """Return a copy so callers can't mutate the real set."""
    return set(_unsynced_groups)

