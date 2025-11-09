import bpy
import time

from ..constants import LICENSE_PRO, LICENSE_STANDARD, PRE, FINISHED
from ..lib import classify_object
from ..lib import group_manager
from .. import engine_state
from ..surface_manager import CLASSIFICATION_ROOT_MARKER_PROP


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
    # BUT: exclude the classification root from being considered a "top"
    coll_to_top = {}

    def traverse(current_coll, current_top):
        for child in current_coll.children:
            coll_to_top[child] = current_top
            traverse(child, current_top)

    # Only consider collections that are NOT classification roots as valid tops
    for top in scene_root.children:
        if top.get(CLASSIFICATION_ROOT_MARKER_PROP, False):
            continue
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
            if not top or top.get(CLASSIFICATION_ROOT_MARKER_PROP, False):
                continue
            if top not in top_has_mesh_cache:
                top_has_mesh_cache[top] = coll_has_mesh(top)
            if top_has_mesh_cache[top]:
                qualifying.append(obj)
                break  # once added, no need to check more collections

    return list(set(qualifying))  # remove duplicates


class Pivot_OT_Standardize_Selected_Groups(bpy.types.Operator):
    """
    Pro Edition: Standardize Selected Groups
    
    Takes user selection, groups objects by collection boundaries and root parents,
    performs classification on entire groups with group guessing in the engine.
    """
    bl_idname = "object." + PRE.lower() + "standardize_selected_groups"
    bl_icon = 'OUTLINER_COLLECTION'
    license_type = engine_state.get_engine_license_status()
    bl_label = "Standardize Selected Groups"
    bl_description = "Standardize selected objects and their groups"
    bl_options = {"REGISTER", "UNDO"}
    

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        return bool(get_qualifying_objects_for_selected(sel, objects_collection))

    def execute(self, context):
        # Exit edit mode if active to ensure mesh data is accessible
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        startTime = time.perf_counter()
        
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        objects = get_qualifying_objects_for_selected(context.selected_objects, objects_collection)
        classify_object.standardize_groups(objects)
        
        endTime = time.perf_counter()
        elapsed = endTime - startTime
        print(f"Standardize Selected Groups completed in {(elapsed) * 1000:.2f}ms")
        engine_state._is_performing_classification = True
        return {FINISHED}


class Pivot_OT_Standardize_Selected_Objects(bpy.types.Operator):
    """
    Pro Edition: Standardize Selected Objects
    
    Standardizes one or more selected objects.
    """
    bl_idname = "object." + PRE.lower() + "standardize_selected_objects"
    bl_label = "Standardize Selected Objects"
    bl_description = "Standardize selected objects"
    bl_options = {"REGISTER", "UNDO"}
    bl_icon = 'OBJECT_DATA'

    @classmethod
    def poll(cls, context):
        sel = getattr(context, "selected_objects", None) or []
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        return bool(get_qualifying_objects_for_selected(sel, objects_collection))

    def execute(self, context):
        # Exit edit mode if active to ensure mesh data is accessible
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        startTime = time.perf_counter()
        
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        objects = get_qualifying_objects_for_selected(context.selected_objects, objects_collection)
        classify_object.standardize_objects(objects)
        
        endTime = time.perf_counter()
        elapsed = endTime - startTime
        print(f"Standardize Selected Objects completed in {(elapsed) * 1000:.2f}ms")
        return {FINISHED}


class Pivot_OT_Standardize_Active_Object(bpy.types.Operator):
    """
    Standard Edition: Standardize Active Object
    
    Standardizes the active object only.
    """
    bl_idname = "object." + PRE.lower() + "standardize_active_object"
    bl_label = "Standardize Active Object"
    bl_description = "Standardize the active object"
    bl_options = {"REGISTER", "UNDO"}
    bl_icon = 'OBJECT_DATA'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        return obj and obj in get_qualifying_objects_for_selected([obj], objects_collection)

    def execute(self, context):
        # Exit edit mode if active to ensure mesh data is accessible
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        startTime = time.perf_counter()
        
        objects_collection = group_manager.get_group_manager().get_objects_collection()
        obj = context.active_object
        if obj and obj in get_qualifying_objects_for_selected([obj], objects_collection):
            classify_object.standardize_objects([obj])
        
        endTime = time.perf_counter()
        elapsed = endTime - startTime
        print(f"Standardize Active Object completed in {(elapsed) * 1000:.2f}ms")
        return {FINISHED}


