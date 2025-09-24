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
from .lib import bridge

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

class Splatter_OT_Align_To_Axes(bpy.types.Operator):
    bl_idname = PRE.lower() + ".align_to_axes"
    bl_label = "Align to Axes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []
        if any(obj.type == 'MESH' for obj in sel):
            return True

        scene_root = context.scene.collection if context and context.scene else None
        if not scene_root or not sel:
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
        rots, locs, root_groups, full_groups, all_local_quats, surface_type, group_names, origin = bridge.align_to_axes_batch(context.selected_objects)
        endCPP = time.perf_counter()
        elapsedCPP = endCPP - startCPP


        startPython = time.perf_counter()
        # Apply results
        obj_idx = 0
        for i, group in enumerate(root_groups):
            delta_quat = rots[i]
            first_obj = group[0]

            for obj in group:
                local_quat = all_local_quats[obj_idx]
                loc = locs[obj_idx]
                
                obj.rotation_quaternion = (delta_quat @ local_quat).normalized()
                obj.location = Vector(loc)
                bpy.context.scene.cursor.location = Vector(origin[i]) + first_obj.location
                obj_idx += 1

        for i, group in enumerate(full_groups):
            surface_type_value = surface_type[i]
            group_name = group_names[i]
            
            # Since the engine is the source of truth, update each object without sending commands back to engine
            if group:  # Make sure group is not empty
                from .property_manager import get_property_manager
                prop_manager = get_property_manager()
                
                # Set group names and surface types for all objects in the group
                for obj in group:
                    if hasattr(obj, "classification"):
                        prop_manager.set_group_name(obj, group_name)
                        prop_manager.set_attribute(obj, 'surface_type', surface_type_value, update_group=False, update_engine=False)
                
                
        
        endPython = time.perf_counter()
        elapsedPython = endPython - startPython
        print(f"Python time elapsed: {elapsedPython * 1000:.2f}ms")
        print(f"Total time elapsed: {(elapsedCPP + elapsedPython) * 1000:.2f}ms")
        return {FINISHED}
