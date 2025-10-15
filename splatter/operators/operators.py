import bpy
import time

from mathutils import Vector
from ..constants import (
    CANCELLED,
    FINISHED,
    PRE,
)

from .. import engine
from ..property_manager import get_property_manager

class Splatter_OT_Organize_Classified_Objects(bpy.types.Operator):
    bl_idname = PRE.lower() + ".organize_classified_objects"
    bl_label = "Organize Classified Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Return true if we have existing groups (checked via collection metadata)
        prop_manager = get_property_manager()
        return prop_manager.has_existing_groups()

    def execute(self, context):
        start_total = time.perf_counter()
        try:
            prop_manager = get_property_manager()
            classifications = prop_manager.collect_group_classifications()
            if classifications:
                sync_ok = prop_manager.sync_group_classifications(classifications)
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
                    objects_in_group = list(prop_manager._iter_group_objects(group_name))
                    if objects_in_group:
                        try:
                            target_pos = Vector((pos[0], pos[1], pos[2]))
                            
                            # Calculate current center of the group to preserve relative positions
                            current_center = sum((obj.location for obj in objects_in_group), Vector((0, 0, 0))) / len(objects_in_group)
                            delta = target_pos - current_center
                            
                            # Move only parent objects in the group by the delta
                            for obj in objects_in_group:
                                if obj.parent is None:
                                    obj.location += delta
                            
                            organized_count += 1
                        except Exception as e:
                            print(f"[Splatter] Failed to organize group '{group_name}': {e}")
                            # print(f"  Raw position data: {pos} (type: {type(pos)})")
                            # print(f"  Full positions response: {positions}")
                            # print(f"  Full engine response: {response}")
                            # Continue to next group instead of failing the whole operation
                
                self.report({"INFO"}, f"Organized {organized_count} object groups")
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
