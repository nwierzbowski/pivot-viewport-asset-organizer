import bpy
import time

from mathutils import Vector

from pivot import engine_state
from ..constants import (
    CANCELLED,
    FINISHED,
    LICENSE_PRO,
    PRE,
)

from .. import engine
from ..surface_manager import get_surface_manager
from ..lib import group_manager

class Pivot_OT_Organize_Classified_Objects(bpy.types.Operator):
    bl_idname = "object." + PRE.lower() + "organize_classified_objects"
    license_type = engine_state.get_engine_license_status()
    bl_label = "Organize Viewport by Group"
    bl_description = "Organize classified objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Return true if we have existing groups (checked via collection metadata)
        group_mgr = group_manager.get_group_manager()
        return group_mgr.has_existing_groups()

    def execute(self, context):
        start_total = time.perf_counter()
        try:
            surface_manager = get_surface_manager()
            classifications = surface_manager.collect_group_classifications()
            if classifications:
                sync_ok = surface_manager.sync_group_classifications(classifications)
                if not sync_ok:
                    self.report({"WARNING"}, "Failed to sync classifications to engine; results may be outdated")

            # Call the engine to organize objects
            start_engine = time.perf_counter()
            engine_comm = engine.get_engine_communicator()
            response = engine_comm.send_command({"id": 1, "op": "organize_objects"})
            end_engine = time.perf_counter()
            
            start_post = time.perf_counter()
            if "positions" in response:
                positions = response["positions"]
                
                # Apply positions to each group using collection-based tracking
                organized_count = 0
                for group_name, pos in positions.items():
                    if group_name not in bpy.data.collections:
                        continue
                    
                    objects_in_group = bpy.data.collections[group_name].objects
                    if not objects_in_group:
                        continue
                    
                    try:
                        target_pos = Vector((pos[0], pos[1], pos[2]))
                        
                        # Move only parent objects in the group directly to the engine-provided position
                        parent_objs = [obj for obj in objects_in_group if obj.parent is None]
                        if not parent_objs:
                            continue

                        for obj in parent_objs:
                            obj.location = target_pos.copy()
                        
                        organized_count += 1
                    except Exception as e:
                        print(f"[Pivot] Failed to organize group '{group_name}': {e}")
                        # Continue to next group instead of failing the whole operation
                
                self.report({"INFO"}, f"Organized {organized_count} object groups")
                engine_state._is_performing_classification = True
            else:
                self.report({"WARNING"}, "No positions returned from engine")
            end_post = time.perf_counter()
                
        except Exception as e:
            end_total = time.perf_counter()
            self.report({"ERROR"}, f"Failed to organize objects: {e}")
            print(f"Organize objects failed - Total time: {(end_total - start_total) * 1000:.2f}ms")
            return {CANCELLED}
        
        end_total = time.perf_counter()
        print(f"Organize objects - Engine call: {(end_engine - start_engine) * 1000:.2f}ms, Post-processing: {(end_post - start_post) * 1000:.2f}ms, Total: {(end_total - start_total) * 1000:.2f}ms")
            
        return {FINISHED}


class Pivot_OT_Upgrade_To_Pro(bpy.types.Operator):
    bl_idname = PRE.lower() + ".upgrade_to_pro"
    bl_label = "Upgrade to Pro"
    bl_description = "Visit our website!"

    def execute(self, context):
        bpy.ops.wm.url_open(url="https://elbo.studio")
        return {FINISHED}
