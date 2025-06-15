import math
import bpy
import random
import bmesh
from .utils import link_node_group
from mathutils import Vector
from .constants import PRE, ROOM_BASE_NG
from bpy.props import FloatProperty, StringProperty

# Internal data storage for volume calculations
_volume_data = {
    "object_name": "",
    "width": 0.0,
    "height": 0.0,
    "depth": 0.0,
    "volume": 0.0,
}


def get_volume_data():
    """Get the current volume data"""
    return _volume_data.copy()


def clear_volume_data():
    """Clear the volume data"""
    global _volume_data
    _volume_data = {
        "object_name": "",
        "width": 0.0,
        "height": 0.0,
        "depth": 0.0,
        "volume": 0.0,
    }


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


class Splatter_OT_Classify_Object(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_object"
    bl_label = "Classify Object"
    bl_options = {"REGISTER", "UNDO"}

    min_area = 0.03  # Minimum area of flat surface to consider
    angle_threshold = 5
    max_angle_threshold = 60
    size_scale_factor = 1

    select_found = True

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

    def execute(self, context):
        obj = context.active_object

        # Get bmesh representation
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.normal_update()

        # Convert angle thresholds to radians
        base_angle_rad = math.radians(self.angle_threshold)
        max_angle_rad = math.radians(self.max_angle_threshold)

        # Find flat surface groups
        flat_surfaces = self.find_flat_surface_groups(
            bm, base_angle_rad, max_angle_rad, self.size_scale_factor, self.min_area
        )

        if self.select_found:
            # Deselect all faces first
            for face in bm.faces:
                face.select = False

            # Select faces in qualifying flat surfaces
            for surface_faces in flat_surfaces:
                for face in surface_faces:
                    face.select = True

        # Update mesh
        bmesh.update_edit_mesh(obj.data)

        self.report(
            {"INFO"}, f"Found {len(flat_surfaces)} flat surfaces meeting criteria"
        )
        return {"FINISHED"}

    def find_flat_surface_groups(
        self, bm, base_angle_threshold, max_angle_threshold, size_scale_factor, min_area
    ):
        """Find groups of connected faces that are approximately coplanar"""
        visited = set()
        flat_surfaces = []

        for face in bm.faces:
            if face.index in visited:
                continue

            # Start a new surface group
            surface_faces = []
            stack = [face]

            while stack:
                current_face = stack.pop()
                if current_face.index in visited:
                    continue

                visited.add(current_face.index)
                surface_faces.append(current_face)

                # Check adjacent faces
                for edge in current_face.edges:
                    for linked_face in edge.link_faces:
                        if (
                            linked_face.index not in visited
                            and self.faces_are_coplanar_adaptive(
                                current_face,
                                linked_face,
                                base_angle_threshold,
                                max_angle_threshold,
                                size_scale_factor,
                            )
                        ):
                            stack.append(linked_face)

            # Calculate total area of this surface group
            total_area = sum(face.calc_area() for face in surface_faces)

            # Calculate average normal properly
            avg_normal = Vector((0, 0, 0))
            for face in surface_faces:
                avg_normal += face.normal
            avg_normal.normalize()

            # Only keep surfaces that meet minimum area requirement
            # Check if surface is mostly horizontal (facing up)
            if total_area >= min_area and avg_normal.z > 0.5:
                flat_surfaces.append(surface_faces)

        return flat_surfaces

    def faces_are_coplanar_adaptive(
        self, face1, face2, base_angle_threshold, max_angle_threshold, size_scale_factor
    ):
        """Check if two faces are approximately coplanar with size-adaptive tolerance"""
        # Calculate angle between face normals
        if face1.normal.length == 0 or face2.normal.length == 0:
            return False
        angle = face1.normal.angle(face2.normal)

        # Calculate combined face size (average area of both faces)
        avg_area = (face1.calc_area() + face2.calc_area()) / 2.0

        # Calculate adaptive angle threshold based on face size
        # Uses logarithmic scaling to prevent extreme values
        size_factor = math.log(1 + avg_area * size_scale_factor)
        adaptive_threshold = base_angle_threshold + (
            max_angle_threshold - base_angle_threshold
        ) * min(size_factor / math.log(1 + size_scale_factor * 10), 1.0)

        return angle <= adaptive_threshold

    def faces_are_coplanar(self, face1, face2, angle_threshold):
        """Check if two faces are approximately coplanar (legacy method)"""
        # Calculate angle between face normals
        angle = face1.normal.angle(face2.normal)
        return angle <= angle_threshold

    def get_surface_info(self, surface_faces):
        """Get information about a surface group"""
        total_area = sum(face.calc_area() for face in surface_faces)

        # Calculate average normal
        avg_normal = Vector((0, 0, 0))
        for face in surface_faces:
            avg_normal += face.normal
        avg_normal.normalize()

        # Calculate bounding box
        all_verts = []
        for face in surface_faces:
            all_verts.extend(face.verts)

        if all_verts:
            min_co = Vector(all_verts[0].co)
            max_co = Vector(all_verts[0].co)

            for vert in all_verts:
                for i in range(3):
                    min_co[i] = min(min_co[i], vert.co[i])
                    max_co[i] = max(max_co[i], vert.co[i])

            dimensions = max_co - min_co
        else:
            dimensions = Vector((0, 0, 0))

        return {
            "area": total_area,
            "face_count": len(surface_faces),
            "normal": avg_normal,
            "dimensions": dimensions,
        }
