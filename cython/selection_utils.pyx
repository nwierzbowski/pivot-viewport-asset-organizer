# selection_utils.pyx - selection and grouping helpers for Blender objects

import bpy


cpdef object get_root_parent(object obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj


cpdef list get_all_mesh_descendants(object root):
    cdef list meshes = []
    if root.type == 'MESH' and len(root.data.vertices) != 0:
        meshes.append(root)
    for child in root.children:
        meshes.extend(get_all_mesh_descendants(child))
    return meshes


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
    """Group selection by scene/collection boundaries.

    Returns a 6-tuple:
      (mesh_groups, parent_groups, group_names, total_verts, total_edges, total_objects)
    """
    cdef object scene_coll = bpy.context.scene.collection
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

    cdef set root_parents = set()
    cdef dict group_map = {}  # top_coll -> list of root_parents
    cdef list scene_roots = []
    cdef list mesh_groups = []
    cdef list parent_groups = []
    cdef list group_names = []
    cdef int total_verts = 0
    cdef int total_edges = 0
    cdef int total_objects = 0
    cdef object obj
    cdef object root
    cdef object coll
    cdef list roots
    cdef list all_meshes
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
        all_meshes = get_all_mesh_descendants(root)
        group_verts = sum(len(m.data.vertices) for m in all_meshes)
        group_edges = sum(len(m.data.edges) for m in all_meshes)
        if group_verts > 0:
            mesh_groups.append(all_meshes)
            parent_groups.append([root])
            group_names.append(root.name + "_O")
            total_verts += group_verts
            total_edges += group_edges
            total_objects += len(all_meshes)

    # For each non-scene group, collect mesh descendants and build groups
    for top_coll, roots in group_map.items():
        all_meshes = []
        for r in roots:
            all_meshes.extend(get_all_mesh_descendants(r))
        group_verts = sum(len(m.data.vertices) for m in all_meshes)
        group_edges = sum(len(m.data.edges) for m in all_meshes)
        if group_verts > 0:
            mesh_groups.append(all_meshes)
            parent_groups.append(roots)
            group_names.append(top_coll.name + "_C")
            total_verts += group_verts
            total_edges += group_edges
            total_objects += len(all_meshes)

    return mesh_groups, parent_groups, group_names, total_verts, total_edges, total_objects
