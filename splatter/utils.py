import os
import bpy

from .constants import ASSETS_FILENAME


def link_node_group(self, node_group_name):
    addon_dir = os.path.dirname(__file__)
    asset_filepath = os.path.join(addon_dir, ASSETS_FILENAME)

    if not os.path.exists(asset_filepath):
        self.report({"ERROR"}, f"Asset file not found! Expected at: {asset_filepath}")
        return {"CANCELLED"}

    if node_group_name not in bpy.data.node_groups:
        try:
            with bpy.data.libraries.load(asset_filepath, link=True) as (
                data_from,
                data_to,
            ):
                if node_group_name in data_from.node_groups:
                    data_to.node_groups = [node_group_name]
                else:
                    self.report(
                        {"ERROR"},
                        f"Node group '{node_group_name}' not in {ASSETS_FILENAME}",
                    )
                    return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Failed to link node group: {e}")
            return {"CANCELLED"}

    ng = bpy.data.node_groups[node_group_name]
    if not ng:
        self.report({"ERROR"}, "Failed to access linked node group.")
        return {"CANCELLED"}

    return ng
