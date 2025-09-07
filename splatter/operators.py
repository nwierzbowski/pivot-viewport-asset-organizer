import math
import bpy
import random
import bmesh
import time

import numpy as np


from .utils import link_node_group
from mathutils import Vector, Quaternion, Euler
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
        
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({ERROR}, "No valid mesh objects selected")
            return {CANCELLED}
        
        # First pass: Collect unique collections from selected objects
        collections_in_selection = set()
        for obj in selected_objects:
            if obj.users_collection:
                coll = obj.users_collection[0]
                if coll != context.scene.collection:
                    collections_in_selection.add(coll)
        
        # Remove individual objects that are in the collected collections
        filtered_objects = []
        # print("Selected objects: ", len(selected_objects))
        for obj in selected_objects:
            # print("Collection 0: ", obj.users_collection)
            if obj.users_collection and obj.users_collection[0] in collections_in_selection:
                continue  # Skip, will be handled as collection
            filtered_objects.append(obj)
        
        # Second pass: Process collections and individual objects
        all_verts = []
        all_edges = []
        all_vert_counts = []
        all_edge_counts = []
        batch_items = []
        all_original_rots = []
        is_grouped = []
        
        # Process collections
        for coll in collections_in_selection:
            coll_objects = [obj for obj in coll.objects if obj.type == 'MESH' and len(obj.data.vertices) > 0]
            if not coll_objects:
                continue
            
            # Collect data for all meshes in collection
            coll_verts = []
            coll_edges = []
            coll_vert_counts = []
            coll_edge_counts = []
            for obj in coll_objects:
                mesh = obj.data
                vert_count = len(mesh.vertices)
                verts_np = np.empty(vert_count * 3, dtype=np.float32)
                mesh.vertices.foreach_get("co", verts_np)
                verts_np.shape = (vert_count, 3)
                coll_verts.append(verts_np)
                
                edge_count = len(mesh.edges)
                edges_np = np.empty(edge_count * 2, dtype=np.uint32)
                mesh.edges.foreach_get("vertices", edges_np)
                edges_np.shape = (edge_count, 2)
                coll_edges.append(edges_np)
                
                coll_vert_counts.append(vert_count)
                coll_edge_counts.append(edge_count)
            
            # Flatten for collection
            total_coll_verts = sum(coll_vert_counts)
            total_coll_edges = sum(coll_edge_counts)
            verts_coll_flat = np.empty((total_coll_verts, 3), dtype=np.float32)
            edges_coll_flat = np.empty((total_coll_edges, 2), dtype=np.uint32)
            
            vert_offset = 0
            edge_offset = 0
            for verts_np, edges_np, v_count, e_count in zip(coll_verts, coll_edges, coll_vert_counts, coll_edge_counts):
                verts_coll_flat[vert_offset:vert_offset + v_count] = verts_np
                edges_coll_flat[edge_offset:edge_offset + e_count] = edges_np
                vert_offset += v_count
                edge_offset += e_count
            
            # Compute offsets and rotations for collection
            first_obj = coll_objects[0]
            offsets = [(obj.location - first_obj.location).to_tuple() for obj in coll_objects]
            rotations = [(obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z) for obj in coll_objects]
            print ("Object rotations: ", rotations)

            # Call grouped alignment for collection
            verts_coll_flat, edges_coll_flat, coll_vert_counts, coll_edge_counts = bridge.align_grouped_min_bounds(verts_coll_flat, edges_coll_flat, coll_vert_counts, coll_edge_counts, offsets, rotations)
            
            # Add to overall buffers
            all_verts.append(verts_coll_flat)
            all_edges.append(edges_coll_flat)
            all_vert_counts.append(total_coll_verts)
            all_edge_counts.append(total_coll_edges)
            batch_items.append(coll_objects)
            all_original_rots.append(rotations)
            is_grouped.append(True)
        
        # Process individual objects
        # print("Filtered objects: ", len(filtered_objects))
        for obj in filtered_objects:
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
            batch_items.append([obj])
            all_original_rots.append([(obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z)])
            is_grouped.append(False)
        
        if all_verts:
            # Flatten all data (collections + individuals)
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
            
            # Call batched C++ function for all
            startCPP = time.perf_counter()
            rots, trans = bridge.align_min_bounds(verts_flat, edges_flat, all_vert_counts, all_edge_counts)
            print(f"rots: {rots}")
            print("original rots: ", all_original_rots)
            endCPP = time.perf_counter()
            elapsedCPP = endCPP - startCPP
            # print("batch items: ", len(batch_items))
            # Apply results
            for i, item in enumerate(batch_items):
                rot = rots[i]
                trans_val = trans[i]
                original_rots = all_original_rots[i]
                print ("rot: ", rot)
                print("original rot: ", original_rots)
                grouped = is_grouped[i]
                delta_euler = Euler(rot, 'XYZ')
                delta_q = delta_euler.to_quaternion()
                for j, obj in enumerate(item):
                    if grouped:
                        orig_euler = Euler(original_rots[j], 'XYZ')
                        orig_q = orig_euler.to_quaternion()
                        if obj.parent:
                            parent_world = obj.parent.matrix_world.to_quaternion()
                            transformed_delta = parent_world.inverted() @ delta_q @ parent_world
                        else:
                            transformed_delta = orig_q.inverted() @ delta_q @ orig_q
                        final_q = orig_q @ transformed_delta
                        obj.rotation_euler = final_q.to_euler('XYZ')
                    else:
                        obj.rotation_euler = delta_euler
                    bpy.context.scene.cursor.location = Vector(trans_val) + obj.location
        
        end = time.perf_counter()
        elapsedPython = end - startPython
        print(f"C++ time elapsed: {elapsedCPP * 1000:.2f}ms")
        print(f"Python time elapsed: {elapsedPython * 1000:.2f}ms")
        return {FINISHED}
