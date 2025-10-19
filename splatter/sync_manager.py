"""
Sync Manager for Splatter.

Orchestrates synchronization operations between the Blender addon and the C++ engine.
"""

from . import engine


def cleanup_orphaned_groups():
    """Clean up orphaned groups: drop from engine and local state.

    This should be called after engine interactions that might create orphans.
    """
    from .lib import group_manager

    group_mgr = group_manager.get_group_manager()
    orphans = group_mgr.get_orphaned_groups()
    if not orphans:
        return 0

    try:
        # Drop from engine cache
        engine_comm = engine.get_engine_communicator()
        dropped_count = engine_comm.drop_groups(orphans)
        if dropped_count < 0:
            print(f"[Splatter] Failed to drop orphaned groups from engine cache")
            return None

        # Clean up locally
        group_mgr.cleanup_orphaned_groups_locally()

        print(f"[Splatter] Cleaned up {dropped_count} orphaned groups")
        return dropped_count
    except Exception as e:
        print(f"[Splatter] Error during orphan cleanup: {e}")
        return None