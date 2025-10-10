# selection_utils.pyx - selection and grouping helpers for Blender objects

import bpy


cpdef object get_root_parent(object obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj


# cpdef list get_all_mesh_descendants(object root):
#     cdef list meshes = []
#     if root.type == 'MESH' and len(root.data.vertices) != 0:
#         meshes.append(root)
#     for child in root.children:
#         meshes.extend(get_all_mesh_descendants(child))
#     return meshes


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


# cpdef list get_all_descendants(object root):
#     cdef list descendants = [root]
#     for child in root.children:
#         descendants.extend(get_all_descendants(child))
#     return descendants


cpdef list get_all_root_objects(object coll):
    cdef list roots = []
    cdef object obj
    for obj in coll.objects:
        if obj.parent is None:
            roots.append(obj)
    for child in coll.children:
        roots.extend(get_all_root_objects(child))
    return roots


def aggregate_object_groups(list selected_objects, object collection):
    """Group selection by scene/collection boundaries.

    Returns a 7-tuple:
      (mesh_groups, parent_groups, full_groups, group_names, total_verts, total_edges, total_objects)
    """
    cdef object depsgraph = bpy.context.evaluated_depsgraph_get()
    cdef object scene_coll = collection
    cdef dict coll_to_top = {}
    cdef object top_coll
    cdef object child_coll
    cdef list stack
    

    # Inline _build_coll_to_top_map to avoid nested function
    for top_coll in scene_coll.children:
        coll_to_top[top_coll] = top_coll
        # Inline build_top_map using iterative approach
        stack = [(top_coll, top_coll)]
        while stack:
            current_coll, current_top = stack.pop()
            for child_coll in current_coll.children:
                coll_to_top[child_coll] = current_top
                stack.append((child_coll, current_top))

    cdef object coll
    cdef object obj

    cdef set root_parents = set()
    cdef dict group_map = {}  # top_coll -> list of root_parents
    cdef list scene_roots = []
    cdef list mesh_groups = []
    cdef list parent_groups = []
    cdef list full_groups = []
    cdef list group_names = []
    cdef int total_verts = 0
    cdef int total_edges = 0
    cdef int total_objects = 0
    
    cdef object root
    cdef list roots
    cdef list all_meshes
    cdef list all_descendants
    cdef int group_verts
    cdef int group_edges

    # Collect unique root parents
    for obj in selected_objects:
        root = get_root_parent(obj)
        root_parents.add(root)

    # Group root parents by top-level collection; treat scene roots individually
    for root in root_parents:
        top_coll = scene_coll
        if root.users_collection:
            coll = root.users_collection[0]
            if coll != scene_coll:
                top_coll = coll_to_top.get(coll, scene_coll)
        if top_coll == scene_coll:
            scene_roots.append(root)
        else:
            if top_coll not in group_map:
                group_map[top_coll] = []
            group_map[top_coll].append(root)

    # For each top_coll with selected roots, include all root objects in it
    for top_coll in list(group_map.keys()):
        roots = get_all_root_objects(top_coll)
        group_map[top_coll] = roots

    # Handle scene roots individually
    for root in scene_roots:
        all_meshes, all_descendants = get_mesh_and_all_descendants(root, depsgraph)
        group_verts = sum(len(m.evaluated_get(depsgraph).data.vertices) for m in all_meshes)
        group_edges = sum(len(m.evaluated_get(depsgraph).data.edges) for m in all_meshes)
        if group_verts > 0:
            mesh_groups.append(all_meshes)
            parent_groups.append([root])
            full_groups.append(all_descendants)
            group_names.append(root.name + "_O")
            total_verts += group_verts
            total_edges += group_edges
            total_objects += len(all_meshes)

    # For each non-scene group, collect mesh descendants and build groups
    for top_coll, roots in group_map.items():
        all_meshes = []
        full_objects = []
        for r in roots:
            meshes, desc = get_mesh_and_all_descendants(r, depsgraph)
            all_meshes.extend(meshes)
            full_objects.extend(desc)
        group_verts = sum(len(m.evaluated_get(depsgraph).data.vertices) for m in all_meshes)
        group_edges = sum(len(m.evaluated_get(depsgraph).data.edges) for m in all_meshes)
        if group_verts > 0:
            mesh_groups.append(all_meshes)
            parent_groups.append(roots)
            full_groups.append(full_objects)
            group_names.append(top_coll.name + "_C")
            total_verts += group_verts
            total_edges += group_edges
            total_objects += len(all_meshes)

    return mesh_groups, parent_groups, full_groups, group_names, total_verts, total_edges, total_objects
