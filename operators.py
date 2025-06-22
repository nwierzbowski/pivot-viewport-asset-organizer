import math
import bpy
import random
import bmesh
from .utils import link_node_group
from mathutils import Vector
from .constants import (
    GET_SURFACES_NG,
    PRE,
    ROOM_BASE_NG,
    SELECT_SEATING,
    SELECT_SURFACES,
    WRITE_SEATING,
    WRITE_SURFACES,
)


class Splatter_OT_Segment_Scene(bpy.types.Operator):
    bl_idname = PRE.lower() + ".segment_scene"
    bl_label = "Segment Scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print("Segment Scene Operator Called (Not Implemented Yet)")
        self.report({"INFO"}, "Scene Segmentation (Not Implemented Yet)")
        return {"FINISHED"}


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

            return {"FINISHED"}
        except Exception as e:
            if obj:
                bpy.data.objects.remove(obj, do_unlink=True)
            mesh_data = obj.data
            if mesh_data:
                bpy.data.meshes.remove(mesh_data)
            self.report({"ERROR"}, f"Failed to generate room: {e}")
            return {"CANCELLED"}


class Splatter_OT_Classify_Base(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_base"
    bl_label = "Classify Base"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        # Separate walls into a separate collection
        obj = bpy.context.object
        # Enter Edit Mode
        bpy.ops.object.mode_set(mode="EDIT")

        # Deselect all faces first
        bpy.ops.mesh.select_all(action="DESELECT")

        # Select faces that are vertical (walls) by checking their normal vectors
        bpy.ops.mesh.select_face_by_sides(number=4, type="EQUAL")  # Select quads
        bpy.ops.object.mode_set(mode="OBJECT")

        # Get selected faces and check if they're vertical

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        # Select vertical faces (walls)
        vertical_faces = []
        for face in bm.faces:
            # Check if face normal is mostly horizontal (wall)
            if abs(face.normal.z) < 0.1:  # Adjust threshold as needed
                face.select = True
                vertical_faces.append(face)
            else:
                face.select = False

        # Update the mesh
        bm.to_mesh(obj.data)
        obj.data.update()
        bm.free()

        # Enter Edit Mode and separate selected faces
        bpy.ops.object.mode_set(mode="EDIT")
        if vertical_faces:
            bpy.ops.mesh.separate(type="SELECTED")

        bpy.ops.object.mode_set(mode="OBJECT")

        # Create or get the walls collection
        walls_collection_name = "Walls"
        if walls_collection_name not in bpy.data.collections:
            walls_collection = bpy.data.collections.new(walls_collection_name)
            bpy.context.scene.collection.children.link(walls_collection)
        else:
            walls_collection = bpy.data.collections[walls_collection_name]

        # Move the separated wall object to the walls collection
        for obj_item in bpy.context.selected_objects:
            if obj_item != obj:  # This is the separated walls object
                # Remove from current collections
                for collection in obj_item.users_collection:
                    collection.objects.unlink(obj_item)
                # Add to walls collection
                walls_collection.objects.link(obj_item)
                obj_item.name = "Room_Walls"

        return {"FINISHED"}


class Splatter_OT_Classify_Faces(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_faces"
    bl_label = "Classify Faces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.mode_set(mode="OBJECT")
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

        bpy.ops.object.mode_set(mode="EDIT")
        getattr(bpy.ops, PRE.lower()).select_surfaces()
        getattr(bpy.ops, PRE.lower()).select_seating()

        return {"FINISHED"}


class Splatter_OT_Select_Surfaces(bpy.types.Operator):
    bl_idname = PRE.lower() + ".select_surfaces"
    bl_label = "Select Surfaces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.mode_set(mode="EDIT")
        link_node_group(self, SELECT_SURFACES)

        bpy.ops.geometry.execute_node_group(name=SELECT_SURFACES)

        return {"FINISHED"}


class Splatter_OT_Selection_To_Surfaces(bpy.types.Operator):
    bl_idname = PRE.lower() + ".selection_to_surfaces"
    bl_label = "Selection to Surfaces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object

        # Ensure the object is in object mode
        if obj.mode != "EDIT":
            self.report({"WARNING"}, "Object must be in Edit Mode")
        else:
            link_node_group(self, WRITE_SURFACES)

            bpy.ops.geometry.execute_node_group(name=WRITE_SURFACES)

        return {"FINISHED"}


class Splatter_OT_Select_Seating(bpy.types.Operator):
    bl_idname = PRE.lower() + ".select_seating"
    bl_label = "Select Seating"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.mode_set(mode="EDIT")
        link_node_group(self, SELECT_SEATING)

        bpy.ops.geometry.execute_node_group(name=SELECT_SEATING)

        return {"FINISHED"}


class Splatter_OT_Selection_To_Seating(bpy.types.Operator):
    bl_idname = PRE.lower() + ".selection_to_seating"
    bl_label = "Selection to Seating"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object

        # Ensure the object is in object mode
        if obj.mode != "EDIT":
            self.report({"WARNING"}, "Object must be in Edit Mode")
        else:
            link_node_group(self, WRITE_SEATING)

            bpy.ops.geometry.execute_node_group(name=WRITE_SEATING)

        return {"FINISHED"}


class Splatter_OT_Classify_Object(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_object"
    bl_label = "Classify Object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = bpy.context.active_object
        if not obj:
            self.report({"ERROR"}, "No active object to classify")
            return {"CANCELLED"}

        bpy.ops.object.mode_set(mode="OBJECT")

        attrs = obj.data.attributes

        isSeating = attrs.get("isSeating")
        isSurface = attrs.get("isSurface")

        # Check if the object has the required classification attributes

        if isSeating is None or isSurface is None:
            self.report(
                {"ERROR"},
                "Object does not have classification attributes, please run classify faces",
            )
            return {"CANCELLED"}

        if isSeating.data_type != "BOOLEAN" or isSurface.data_type != "BOOLEAN":
            self.report(
                {"ERROR"},
                "Classification attributes must be boolean type, please run classify faces",
            )
            return {"CANCELLED"}

        if isSeating.domain != "FACE" or isSurface.domain != "FACE":
            self.report(
                {"ERROR"},
                "Classification attributes must be face domain, please run classify faces",
            )
            return {"CANCELLED"}

        obj.classification.isSeating = any(item.value for item in isSeating.data)
        obj.classification.isSurface = any(item.value for item in isSurface.data)

        return {"FINISHED"}
