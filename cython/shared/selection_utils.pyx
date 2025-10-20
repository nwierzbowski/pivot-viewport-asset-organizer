# selection_utils.pyx - selection and grouping helpers for Blender objects

import bpy
from . import edition_utils
from splatter.surface_manager import CLASSIFICATION_MARKER_PROP
from collections import defaultdict


cpdef object get_root_object(object obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj

cpdef tuple get_mesh_and_all_descendants(object root, object depsgraph):
    cdef list meshes = []
    cdef list descendants = [root]
    cdef list stack = [root]
    cdef object current
    cdef object eval_obj
    cdef object eval_mesh
    while stack:
        current = stack.pop()
        if current.type == 'MESH':
            eval_obj = current.evaluated_get(depsgraph)
            eval_mesh = eval_obj.data
            if len(eval_mesh.vertices) != 0:
                meshes.append(current)
        for child in current.children:
            descendants.append(child)
            stack.append(child)
    return meshes, descendants


cpdef bint has_mesh_with_vertices(object root, object depsgraph):
    cdef list stack = [root]
    cdef object current
    cdef object eval_obj
    cdef object eval_mesh
    while stack:
        current = stack.pop()
        if current.type == 'MESH':
            eval_obj = current.evaluated_get(depsgraph)
            eval_mesh = eval_obj.data
            if len(eval_mesh.vertices) > 0:
                return True
        for child in current.children:
            stack.append(child)
    return False


cpdef list get_all_root_objects(object coll):
    cdef list roots = []
    cdef object obj
    for obj in coll.objects:
        if obj.parent is None:
            roots.append(obj)
    for child in coll.children:
        roots.extend(get_all_root_objects(child))
    return roots


def aggregate_object_groups(list selected_objects):
    """Group the selection by collection boundaries and root parents."""

    if edition_utils.is_standard_edition() and len(selected_objects) != 1:
        raise ValueError("Standard edition only supports single object selection")

    cdef object depsgraph
    cdef object scene_coll
    cdef object coll_to_top_map
    cdef object top_coll
    cdef object child_coll
    cdef list stack

    cdef set root_objects
    cdef list mesh_groups
    cdef list parent_groups
    cdef list full_groups
    cdef list group_names
    cdef int total_verts
    cdef int total_edges
    cdef int total_objects

    cdef object new_coll
    cdef object processed_coll
    cdef set collections_to_process
    # Get the configured objects collection
    from . import group_manager
    scene_coll = group_manager.get_group_manager().get_objects_collection()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # Build a lookup that points every nested collection back to its top-level owner.
    coll_to_top_map = defaultdict(list)
    stack = []
    for top_coll in scene_coll.children:
        if top_coll.get(CLASSIFICATION_MARKER_PROP, False):
            continue
        coll_to_top_map[top_coll].append(top_coll)
        stack = [(top_coll, top_coll)]
        while stack:
            current_coll, current_top = stack.pop()
            for child_coll in current_coll.children:
                coll_to_top_map[child_coll].append(current_top)
                stack.append((child_coll, current_top))

    root_objects = set()
    mesh_groups = []
    parent_groups = []
    full_groups = []
    group_names = []
    total_verts = 0
    total_edges = 0
    total_objects = 0

    root_obj = None
    meshes = []
    descendants = []
    top_roots = []
    group_verts = 0
    group_edges = 0

    # Deduplicate root parents to avoid processing the same hierarchy multiple times.
    for obj in selected_objects:
        root_obj = get_root_object(obj)
        root_objects.add(root_obj)

    # First pass: accumulate collections to process, creating new ones where needed.
    collections_to_process = set()
    for root_obj in root_objects:
        if not has_mesh_with_vertices(root_obj, depsgraph):
            continue
        for coll in root_obj.users_collection:
            if coll == scene_coll:
                new_coll = bpy.data.collections.new(root_obj.name)
                scene_coll.objects.unlink(root_obj)
                scene_coll.children.link(new_coll)
                new_coll.objects.link(root_obj)
                collections_to_process.add(new_coll)
            elif coll in coll_to_top_map:
                for top in coll_to_top_map[coll]:
                    collections_to_process.add(top)

    # Second pass: build groups for each collection.
    for processed_coll in collections_to_process:
        top_roots = get_all_root_objects(processed_coll)
        meshes = []
        descendants = []
        for root_obj in top_roots:
            root_meshes, root_descendants = get_mesh_and_all_descendants(root_obj, depsgraph)
            meshes.extend(root_meshes)
            descendants.extend(root_descendants)
        group_verts = 0
        group_edges = 0
        for m in meshes:
            eval_obj = m.evaluated_get(depsgraph)
            eval_mesh = eval_obj.data
            group_verts += len(eval_mesh.vertices)
            group_edges += len(eval_mesh.edges)
        mesh_groups.append(meshes)
        parent_groups.append(top_roots)
        full_groups.append(descendants)
        group_names.append(processed_coll.name)
        total_verts += group_verts
        total_edges += group_edges
        total_objects += len(meshes)

    return mesh_groups, parent_groups, full_groups, group_names, total_verts, total_edges, total_objects
