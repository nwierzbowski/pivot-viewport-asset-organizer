import bpy
import time

from mathutils import Vector
from ..constants import (
    CANCELLED,
    FINISHED,
    PRE,
)

from .. import engine
from ..engine_state import get_engine_has_groups_cached, get_engine_parent_groups

class Splatter_OT_Organize_Classified_Objects(bpy.types.Operator):
    bl_idname = PRE.lower() + ".organize_classified_objects"
    bl_label = "Organize Classified Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Return true if we have successfully classified objects (cached)
        return get_engine_has_groups_cached()

    def execute(self, context):
        start_total = time.perf_counter()
        try:
            # Call the engine to organize objects
            start_engine = time.perf_counter()
            engine_comm = engine.get_engine_communicator()
            response = engine_comm.send_command({"id": 1, "op": "organize_objects"})
            end_engine = time.perf_counter()
            
            start_post = time.perf_counter()
            if "positions" in response:
                positions = response["positions"]
                
                # Get the cached parent groups dictionary
                parent_groups = get_engine_parent_groups()
                
                # Apply positions to each group
                organized_count = 0
                for group_name, pos in positions.items():
                    if group_name in parent_groups:
                        target_pos = Vector((pos[0], pos[1], pos[2]))
                        
                        # Get all parent objects in this group (these are the ones that need to be moved)
                        group_data = parent_groups[group_name]
                        parent_objects = group_data['objects']
                        offsets = group_data['offsets']

                        # Apply positions to each parent object using its offset + target position
                        for i, obj in enumerate(parent_objects):
                            obj_offset = Vector(offsets[i]) if i < len(offsets) else Vector((0, 0, 0))
                            obj.location = target_pos + obj_offset
                        
                        organized_count += 1
                
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
