import math
import bpy
import random
import time

from .utils import link_node_group
from mathutils import Vector
from .constants import (
    BOOLEAN,
    CANCELLED,
    CLASSIFY_ROOM,
    EDIT,
    ERROR,
    INFO,
    FACE,
    FACE_ATTR_IS_SEATING,
    FACE_ATTR_IS_SURFACE,
    FINISHED,
    GET_SURFACES_NG,
    OBJECT,
    PRE,
    ROOM_BASE_NG,
    SELECT,
    SELECT_SEATING,
    SELECT_SURFACES,
    WARNING,
    WRITE_SEATING,
    WRITE_SURFACES,
)
from .lib import classify_object
from . import engine
from .engine_state import get_engine_has_groups_cached, set_engine_has_groups_cached, get_engine_parent_groups

class Splatter_OT_Segment_Scene(bpy.types.Operator):
    bl_idname = PRE.lower() + ".segment_scene"
    bl_label = "Segment Scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print("Segment Scene Operator Called (Not Implemented Yet)")
        self.report({"INFO"}, "Scene Segmentation (Not Implemented Yet)")
        return {FINISHED}


class Splatter_OT_Generate_Base(bpy.types.Operator):
    bl_idname = PRE.lower() + ".generate_base"
    bl_label = "Generate Base"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            ng = link_node_group(self, ROOM_BASE_NG)

            bpy.ops.mesh.primitive_plane_add(align="WORLD", location=(0, 0, 0))

            obj = bpy.context.object

            modifier = obj.modifiers.new(name=ROOM_BASE_NG, type="NODES")
            modifier.node_group = ng
            inputs = ng.interface.items_tree

            # Set values for the inputs
            modifier[inputs["min_dist"].identifier] = 1.3
            modifier[inputs["seed"].identifier] = random.randint(-999999, 999999)
            modifier[inputs["spread"].identifier] = 1
            modifier[inputs["size_var"].identifier][0] = 1.8
            modifier[inputs["size_var"].identifier][1] = 1.8
            modifier[inputs["size_var"].identifier][2] = 1.2
            modifier[inputs["base_size"].identifier] = 2.7

            bpy.ops.object.modifier_apply(modifier=ROOM_BASE_NG)

            bpy.ops.object.origin_set(type="ORIGIN_CENTER_OF_VOLUME", center="MEDIAN")

            z_loc = obj.location.z
            bpy.ops.object.location_clear()
            bpy.ops.transform.translate(value=(0, 0, z_loc))

            bpy.context.scene.cursor.location = Vector((0.0, 0.0, 0.0))
            bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")

            bpy.ops.object.mode_set(mode=EDIT)
            bpy.ops.mesh.select_all(action=SELECT)
            bpy.ops.mesh.flip_normals()
            bpy.ops.object.mode_set(mode=OBJECT)

            return {FINISHED}
        except Exception as e:
            if obj:
                bpy.data.objects.remove(obj, do_unlink=True)
            mesh_data = obj.data
            if mesh_data:
                bpy.data.meshes.remove(mesh_data)
            self.report({ERROR}, f"Failed to generate room: {e}")
            return {CANCELLED}


class Splatter_OT_Classify_Base(bpy.types.Operator):
    """Classify and separate room base into walls, floors, and ceilings"""

    bl_idname = PRE.lower() + ".classify_base"
    bl_label = "Classify Base"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != "MESH":
            self.report({ERROR}, "No active mesh object selected")
            return {CANCELLED}

        ng = link_node_group(self, CLASSIFY_ROOM)
        modifier = obj.modifiers.new(name=CLASSIFY_ROOM, type="NODES")
        modifier.node_group = ng
        bpy.ops.object.modifier_apply(modifier=CLASSIFY_ROOM)

        return {FINISHED}


class Splatter_OT_Classify_Faces(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_faces"
    bl_label = "Classify Faces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.mode_set(mode=OBJECT)
        obj = context.active_object

        ng = link_node_group(self, GET_SURFACES_NG)

        modifier = obj.modifiers.new(name=GET_SURFACES_NG, type="NODES")
        modifier.node_group = ng
        inputs = ng.interface.items_tree

        # Set values for the inputs
        modifier[inputs["min_surface_size"].identifier] = 0.03
        modifier[inputs["min_clearance"].identifier] = 0.2
        modifier[inputs["min_z_norm"].identifier] = (
            10 * math.pi / 180
        )  # Convert degrees to radians

        bpy.ops.object.modifier_apply(modifier=GET_SURFACES_NG)

        bpy.ops.object.mode_set(mode=EDIT)
        getattr(bpy.ops, PRE.lower()).select_surfaces()
        getattr(bpy.ops, PRE.lower()).select_seating()

        return {FINISHED}


class Splatter_OT_Select_Surfaces(bpy.types.Operator):
    bl_idname = PRE.lower() + ".select_surfaces"
    bl_label = "Select Surfaces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.mode_set(mode=EDIT)
        link_node_group(self, SELECT_SURFACES)

        bpy.ops.geometry.execute_node_group(name=SELECT_SURFACES)

        return {FINISHED}


class Splatter_OT_Selection_To_Surfaces(bpy.types.Operator):
    bl_idname = PRE.lower() + ".selection_to_surfaces"
    bl_label = "Selection to Surfaces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object

        # Ensure the object is in object mode
        if obj.mode != EDIT:
            self.report({WARNING}, "Object must be in Edit Mode")
        else:
            link_node_group(self, WRITE_SURFACES)

            bpy.ops.geometry.execute_node_group(name=WRITE_SURFACES)

        return {FINISHED}


class Splatter_OT_Select_Seating(bpy.types.Operator):
    bl_idname = PRE.lower() + ".select_seating"
    bl_label = "Select Seating"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.mode_set(mode=EDIT)
        link_node_group(self, SELECT_SEATING)

        bpy.ops.geometry.execute_node_group(name=SELECT_SEATING)

        return {FINISHED}


class Splatter_OT_Selection_To_Seating(bpy.types.Operator):
    bl_idname = PRE.lower() + ".selection_to_seating"
    bl_label = "Selection to Seating"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object

        # Ensure the object is in object mode
        if obj.mode != EDIT:
            self.report({WARNING}, "Object must be in Edit Mode")
        else:
            link_node_group(self, WRITE_SEATING)

            bpy.ops.geometry.execute_node_group(name=WRITE_SEATING)

        return {FINISHED}


class Splatter_OT_Classify_Object(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_object"
    bl_label = "Classify Object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = bpy.context.active_object
        if not obj:
            self.report({ERROR}, "No active object to classify")
            return {CANCELLED}

        bpy.ops.object.mode_set(mode=OBJECT)

        attrs = obj.data.attributes

        isSeating = attrs.get(FACE_ATTR_IS_SEATING)
        isSurface = attrs.get(FACE_ATTR_IS_SURFACE)

        # Check if the object has the required classification attributes

        if isSeating is None or isSurface is None:
            self.report(
                {ERROR},
                "Object does not have classification attributes, please run classify faces",
            )
            return {CANCELLED}

        if isSeating.data_type != BOOLEAN or isSurface.data_type != BOOLEAN:
            self.report(
                {ERROR},
                "Classification attributes must be boolean type, please run classify faces",
            )
            return {CANCELLED}

        if isSeating.domain != FACE or isSurface.domain != FACE:
            self.report(
                {ERROR},
                "Classification attributes must be face domain, please run classify faces",
            )
            return {CANCELLED}

        obj.classification.isSeating = any(item.value for item in isSeating.data)
        obj.classification.isSurface = any(item.value for item in isSurface.data)

        return {FINISHED}

class Splatter_OT_Classify_Selected_Objects(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_selected_objects"
    bl_label = "Classify Selected"
    bl_description = "Classify selected objects in Objects collection"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []

        if context.scene.splatter.objects_collection:
            scene_root = context.scene.splatter.objects_collection
        else:
            scene_root = context.scene.collection if context and context.scene else None
        if not sel:
            return False

        # Build a map of every nested collection to its top-level (direct child of scene_root)
        coll_to_top = {}

        def traverse(current_coll, current_top):
            for child in current_coll.children:
                coll_to_top[child] = current_top
                traverse(child, current_top)

        for top in scene_root.children:
            coll_to_top[top] = top
            traverse(top, top)

        # Cache for whether a top-level collection's subtree contains any mesh
        top_has_mesh_cache = {}

        def coll_has_mesh(coll):
            # Fast boolean check: any mesh in this collection or its children
            for o in coll.objects:
                if o.type == 'MESH':
                    return True
            for child in coll.children:
                if coll_has_mesh(child):
                    return True
            return False

        for obj in sel:
            # Consider all collections the object belongs to
            for coll in getattr(obj, 'users_collection', []) or []:
                if coll is scene_root:
                    continue
                top = coll_to_top.get(coll)
                if not top:
                    continue
                if top not in top_has_mesh_cache:
                    top_has_mesh_cache[top] = coll_has_mesh(top)
                if top_has_mesh_cache[top]:
                    return True

        return False

    def execute(self, context):
        startCPP = time.perf_counter()
        
        # Determine which collection to use
        objects_collection = context.scene.splatter.objects_collection or context.scene.collection
        
        classify_object.classify_and_apply_objects(context.selected_objects, objects_collection)
        endCPP = time.perf_counter()
        elapsedCPP = endCPP - startCPP
        print(f"Total time elapsed: {(elapsedCPP) * 1000:.2f}ms")
        
        # Mark that we now have classified objects/groups
        set_engine_has_groups_cached(True)
        
        return {FINISHED}

class Splatter_OT_Classify_All_Objects_In_Collection(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_all_objects_in_collection"
    bl_label = "Classify Collection"
    bl_description = "Classify all objects in Objects collection"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        objects_collection = context.scene.splatter.objects_collection or context.scene.collection

        def has_mesh_in_collection(coll):
            for obj in coll.objects:
                if obj.type == 'MESH':
                    return True
            for child in coll.children:
                if has_mesh_in_collection(child):
                    return True
            return False

        return has_mesh_in_collection(objects_collection)

    def execute(self, context):
        startCPP = time.perf_counter()
        
        # Determine which collection to use
        objects_collection = context.scene.splatter.objects_collection or context.scene.collection
        
        def get_all_mesh_objects_in_collection(coll):
            meshes = []
            for obj in coll.objects:
                if obj.type == 'MESH':
                    meshes.append(obj)
            for child in coll.children:
                meshes.extend(get_all_mesh_objects_in_collection(child))
            return meshes
        
        all_objects = get_all_mesh_objects_in_collection(objects_collection)
        
        classify_object.classify_and_apply_objects(all_objects, objects_collection)
        endCPP = time.perf_counter()
        elapsedCPP = endCPP - startCPP
        print(f"Total time elapsed: {(elapsedCPP) * 1000:.2f}ms")
        
        # Mark that we now have classified objects/groups
        set_engine_has_groups_cached(True)
        
        return {FINISHED}

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
