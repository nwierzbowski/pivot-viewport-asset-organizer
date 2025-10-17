import bpy
import time

from ..constants import PRE, FINISHED
from .. import constants
from ..lib import classify_object
from ..group_manager import get_group_manager


def get_all_mesh_objects_in_collection(coll):
    meshes = []
    for obj in coll.objects:
        if obj.type == 'MESH':
            meshes.append(obj)
    for child in coll.children:
        meshes.extend(get_all_mesh_objects_in_collection(child))
    return meshes


def get_qualifying_objects_for_selected(selected_objects, objects_collection):
    qualifying = []
    scene_root = objects_collection
    for obj in selected_objects:
        if obj.type == 'MESH' and scene_root in obj.users_collection:
            qualifying.append(obj)

    # Check for selected objects in scene_root that have mesh descendants
    def has_mesh_descendants(obj):
        for child in obj.children:
            if child.type == 'MESH' or has_mesh_descendants(child):
                return True
        return False

    for obj in selected_objects:
        if scene_root in obj.users_collection and has_mesh_descendants(obj):
            qualifying.append(obj)

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

    for obj in selected_objects:
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
                qualifying.append(obj)
                break  # once added, no need to check more collections

    return list(set(qualifying))  # remove duplicates


def perform_classification(objects):
    constants._is_performing_classification = True
    startCPP = time.perf_counter()
    
    classify_object.classify_and_apply_objects(objects)
    endCPP = time.perf_counter()
    elapsedCPP = endCPP - startCPP
    print(f"Total time elapsed: {(elapsedCPP) * 1000:.2f}ms")


class Splatter_OT_Classify_Selected(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_selected_objects"
    bl_label = "Classify Selected"
    bl_description = "Classify selected objects in Objects collection"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []
        objects_collection = get_group_manager().get_objects_collection()
        return bool(get_qualifying_objects_for_selected(sel, objects_collection))

    def execute(self, context):
        objects_collection = get_group_manager().get_objects_collection()
        objects = get_qualifying_objects_for_selected(context.selected_objects, objects_collection)
        perform_classification(objects)
        return {FINISHED}


class Splatter_OT_Classify_Active_Object(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_active_object"
    bl_label = "Classify Active"
    bl_description = "Classify the active object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        objects_collection = get_group_manager().get_objects_collection()
        return obj and obj in get_qualifying_objects_for_selected([obj], objects_collection)

    def execute(self, context):
        objects_collection = get_group_manager().get_objects_collection()
        objects = get_qualifying_objects_for_selected([context.active_object], objects_collection)
        perform_classification(objects)
        return {FINISHED}


class Splatter_OT_Classify_All_Objects_In_Collection(bpy.types.Operator):
    bl_idname = PRE.lower() + ".classify_all_objects_in_collection"
    bl_label = "Classify Collection"
    bl_description = "Classify all objects in Objects collection"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        objects_collection = get_group_manager().get_objects_collection()
        return bool(get_all_mesh_objects_in_collection(objects_collection))

    def execute(self, context):
        objects_collection = get_group_manager().get_objects_collection()
        objects = get_all_mesh_objects_in_collection(objects_collection)
        perform_classification(objects)
        return {FINISHED}