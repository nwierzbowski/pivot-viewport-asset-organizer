from libc.stdint cimport uint32_t
from libc.stdlib cimport malloc, free
from libc.string cimport memcpy
from mathutils import Quaternion as MathutilsQuaternion

import bpy
import numpy as np
import time

from splatter.cython_api.engine_api cimport prepare_object_batch as prepare_object_batch_cpp
from splatter.cython_api.engine_api cimport group_objects as group_objects_cpp
from splatter.cython_api.engine_api cimport apply_rotation as apply_rotation_cpp

from splatter.cython_api.vec_api cimport Vec3, uVec2i
from splatter.cython_api.quaternion_api cimport Quaternion

def align_min_bounds(float[:, ::1] verts_flat, uint32_t[:, ::1] edges_flat, list vert_counts, list edge_counts):
    cdef uint32_t num_objects = len(vert_counts)
    if num_objects == 0:
        return [], []
    
    # Pre-copy Python lists to C arrays for nogil access
    cdef uint32_t *vert_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef uint32_t *edge_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    for i in range(num_objects):
        vert_counts_ptr[i] = vert_counts[i]
        edge_counts_ptr[i] = edge_counts[i]
    
    cdef Vec3 *verts_ptr = <Vec3 *> &verts_flat[0, 0]   
    cdef uVec2i *edges_ptr = <uVec2i *> &edges_flat[0, 0]
    
    cdef Quaternion *out_rots = <Quaternion *> malloc(num_objects * sizeof(Quaternion))
    cdef Vec3 *out_trans = <Vec3 *> malloc(num_objects * sizeof(Vec3))
    
    with nogil:

        prepare_object_batch_cpp(verts_ptr, edges_ptr, vert_counts_ptr, edge_counts_ptr, num_objects, out_rots, out_trans)
    
    # Convert results to Python lists
    rots = [MathutilsQuaternion((out_rots[i].w, out_rots[i].x, out_rots[i].y, out_rots[i].z)) for i in range(num_objects)]
    trans = [(out_trans[i].x, out_trans[i].y, out_trans[i].z) for i in range(num_objects)]
    
    free(vert_counts_ptr)
    free(edge_counts_ptr)
    free(out_rots)
    free(out_trans)
    
    return rots, trans

def group_objects(float[:, ::1] verts_flat, uint32_t[:, ::1] edges_flat, list vert_counts, list edge_counts, list offsets, list rotations):
    cdef uint32_t num_objects = len(vert_counts)
    if num_objects == 0:
        return verts_flat, edges_flat, [0], [0]
    
    # Calculate total sizes
    cdef uint32_t total_verts = 0
    cdef uint32_t total_edges = 0
    for i in range(num_objects):
        total_verts += vert_counts[i]
        total_edges += edge_counts[i]
    
    # Copy verts_flat and edges_flat to avoid modifying originals
    cdef Vec3 *verts_copy = <Vec3 *>malloc(total_verts * sizeof(Vec3))
    cdef uVec2i *edges_copy = <uVec2i *>malloc(total_edges * sizeof(uVec2i))
    memcpy(verts_copy, &verts_flat[0, 0], total_verts * sizeof(Vec3))
    memcpy(edges_copy, &edges_flat[0, 0], total_edges * sizeof(uVec2i))
    
    # Pre-copy Python lists to C arrays
    cdef uint32_t *vert_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef uint32_t *edge_counts_ptr = <uint32_t *>malloc(num_objects * sizeof(uint32_t))
    cdef Vec3 *offsets_ptr = <Vec3 *>malloc(num_objects * sizeof(Vec3))
    cdef Quaternion *rotations_ptr = <Quaternion *>malloc(num_objects * sizeof(Quaternion))
    for i in range(num_objects):
        vert_counts_ptr[i] = vert_counts[i]
        edge_counts_ptr[i] = edge_counts[i]
        offsets_ptr[i] = Vec3(offsets[i][0], offsets[i][1], offsets[i][2])
        rotations_ptr[i] = Quaternion(rotations[i].w, rotations[i].x, rotations[i].y, rotations[i].z)

    with nogil:
        group_objects_cpp(verts_copy, edges_copy, vert_counts_ptr, edge_counts_ptr, offsets_ptr, rotations_ptr, num_objects)
    
    # Copy back to the input arrays (modify in place for the caller)
    memcpy(&verts_flat[0, 0], verts_copy, total_verts * sizeof(Vec3))
    memcpy(&edges_flat[0, 0], edges_copy, total_edges * sizeof(uVec2i))
    
    free(verts_copy)
    free(edges_copy)
    free(vert_counts_ptr)
    free(edge_counts_ptr)
    free(offsets_ptr)
    free(rotations_ptr)
    
    # Return modified arrays and counts for the combined object
    return verts_flat, edges_flat, [total_verts], [total_edges]

def apply_rotation(float[:, ::1] verts, uint32_t vert_count, rotation):
    cdef Vec3 *verts_ptr = <Vec3 *> &verts[0, 0]
    cdef Quaternion rot = Quaternion(rotation.w, rotation.x, rotation.y, rotation.z)
    with nogil:
        apply_rotation_cpp(verts_ptr, vert_count, rot) 

def align_to_axes_batch(list selected_objects):
    start_prep = time.perf_counter()
    cdef list all_verts = []
    cdef list all_edges = []
    cdef list all_vert_counts = []
    cdef list all_edge_counts = []
    cdef list batch_items = []
    cdef list all_original_rots = []  # flat list of tuples
    
    cdef int total_verts
    cdef int total_edges
    cdef int vert_offset
    cdef int edge_offset
    cdef list rots
    cdef list trans
    
    cdef float[:, ::1] verts_view
    
    # First pass: Collect unique collections from selected objects
    cdef set collections_in_selection = set()
    cdef object obj
    cdef object coll
    for obj in selected_objects:
        if obj.users_collection:
            coll = obj.users_collection[0]
            if coll != bpy.context.scene.collection:
                collections_in_selection.add(coll)
    
    # Remove individual objects that are in the collected collections
    cdef list filtered_objects = []
    for obj in selected_objects:
        if obj.users_collection and obj.users_collection[0] in collections_in_selection:
            continue
        filtered_objects.append(obj)
    
    end_prep = time.perf_counter()
    print(f"Preparation time elapsed: {(end_prep - start_prep) * 1000:.2f}ms")

    start_collections = time.perf_counter()
    # Process collections
    cdef list coll_objects
    cdef list coll_verts
    cdef list coll_edges
    cdef list coll_vert_counts
    cdef list coll_edge_counts
    cdef object mesh
    cdef int vert_count
    cdef int edge_count
    cdef int total_coll_verts
    cdef int total_coll_edges
    cdef list offsets
    cdef list rotations
    cdef object first_obj
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
            verts_view = verts_np
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
        rotations = [obj.rotation_quaternion for obj in coll_objects]

        # Group objects in collection
        verts_coll_flat, edges_coll_flat, coll_vert_counts, coll_edge_counts = group_objects(verts_coll_flat, edges_coll_flat, coll_vert_counts, coll_edge_counts, offsets, rotations)
        
        # Add to overall buffers
        all_verts.append(verts_coll_flat)
        all_edges.append(edges_coll_flat)
        all_vert_counts.append(total_coll_verts)
        all_edge_counts.append(total_coll_edges)
        batch_items.append(coll_objects)
        for obj in coll_objects:
            all_original_rots.extend(rotations)

    end_collections = time.perf_counter()
    print(f"Collection processing time elapsed: {(end_collections - start_collections) * 1000:.2f}ms")

    start_individual = time.perf_counter()
    # Process individual objects
    for obj in filtered_objects:
        mesh = obj.data
        vert_count = len(mesh.vertices)
        if vert_count == 0:
            continue
        
        verts_np = np.empty(vert_count * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", verts_np)
        verts_np.shape = (vert_count, 3)
        verts_view = verts_np
        all_verts.append(verts_np)
        
        edge_count = len(mesh.edges)
        edges_np = np.empty(edge_count * 2, dtype=np.uint32)
        mesh.edges.foreach_get("vertices", edges_np)
        edges_np.shape = (edge_count, 2)
        all_edges.append(edges_np)
        
        all_vert_counts.append(vert_count)
        all_edge_counts.append(edge_count)
        batch_items.append([obj])
        all_original_rots.append(obj.rotation_quaternion)

        apply_rotation(verts_view, vert_count, obj.rotation_quaternion)
    
    end_individual = time.perf_counter()
    print(f"Individual processing time elapsed: {(end_individual - start_individual) * 1000:.2f}ms")

    start_alignment = time.perf_counter()

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
        rots, trans = align_min_bounds(verts_flat, edges_flat, all_vert_counts, all_edge_counts)

        end_alignment = time.perf_counter()
        print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")
        
        return rots, trans, batch_items, all_original_rots
    else:
        end_alignment = time.perf_counter()
        print(f"Alignment time elapsed: {(end_alignment - start_alignment) * 1000:.2f}ms")
        return [], [], [], []