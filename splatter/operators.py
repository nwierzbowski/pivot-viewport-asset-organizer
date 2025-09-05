import math
import bpy
import random
import bmesh
import time

import numpy as np


from .logic.context import edit_bmesh, object_bmesh, object_mode
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

from . import bridge


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
        return any(obj for obj in context.selected_objects if obj.type == 'MESH')

    def execute(self, context):
        startPython = time.perf_counter()
        
        # Collect data for all selected mesh objects
        all_verts = []
        all_edges = []
        all_vert_counts = []
        all_edge_counts = []
        valid_objects = []
        
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            mesh = obj.data
            vert_count = len(mesh.vertices)
            if vert_count == 0:
                continue
            
            verts_np = np.empty(vert_count * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", verts_np)
            verts_np.shape = (vert_count, 3)
            all_verts.append(verts_np)
            
            edge_count = len(mesh.edges)
            edges_np = np.empty(edge_count * 2, dtype=np.uint32)
            mesh.edges.foreach_get("vertices", edges_np)
            edges_np.shape = (edge_count, 2)
            all_edges.append(edges_np)
            
            all_vert_counts.append(vert_count)
            all_edge_counts.append(edge_count)
            valid_objects.append(obj)
        
        if not valid_objects:
            self.report({ERROR}, "No valid mesh objects selected")
            return {CANCELLED}
        
        # Flatten verts and edges into single contiguous arrays
        total_verts = sum(all_vert_counts)
        total_edges = sum(all_edge_counts)
        verts_flat = np.empty((total_verts, 3), dtype=np.float32)
        edges_flat = np.empty((total_edges, 2), dtype=np.uint32)
        
        vert_offset = 0
        edge_offset = 0
        for verts_np, edges_np, v_count, e_count in zip(all_verts, all_edges, all_vert_counts, all_edge_counts):
            verts_flat[vert_offset:vert_offset + v_count] = verts_np
            edges_flat[edge_offset:edge_offset + e_count] = edges_np
            vert_offset += v_count
            edge_offset += e_count
        
        # Call batched C++ function with flattened arrays
        startCPP = time.perf_counter()
        rots, trans = bridge.align_min_bounds(verts_flat, edges_flat, all_vert_counts, all_edge_counts)
        endCPP = time.perf_counter()
        elapsedCPP = endCPP - startCPP
        
        # Apply results in order
        for i, obj in enumerate(valid_objects):
            obj.rotation_euler = rots[i]
            bpy.context.scene.cursor.location = Vector(trans[i]) + obj.location
        
        end = time.perf_counter()
        elapsedPython = end - startPython
        print(f"C++ time elapsed: {elapsedCPP * 1000:.2f}ms")
        print(f"Python time elapsed: {elapsedPython * 1000:.2f}ms")
        return {FINISHED}
