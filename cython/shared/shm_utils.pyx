import numpy as np
cimport numpy as cnp
import uuid
import multiprocessing.shared_memory as shared_memory
import bpy
import platform
from mathutils import Matrix, Vector
from libc.stdint cimport uint32_t
from libc.stddef cimport size_t

def create_data_arrays(uint32_t total_verts, uint32_t total_edges, uint32_t total_objects, list mesh_groups, list pivots, bint is_group_mode):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts_size = total_verts * 3 * 4  # float32 = 4 bytes
    edges_size = total_edges * 2 * 4  # uint32 = 4 bytes
    rotations_size = total_objects * 4 * 4  # float32 = 4 bytes
    scales_size = total_objects * 3 * 4
    offsets_size = total_objects * 3 * 4

    # Platform-aware shared memory names
    # POSIX (macOS, Linux): Use leading '/' for namespace isolation
    # Windows: No leading '/', names are managed by Boost's windows_shared_memory
    # macOS has a 31-char limit for POSIX shared memory names
    is_windows = platform.system() == "Windows"
    prefix = "" if is_windows else "/"
    uid = uuid.uuid4().hex[:16]  # Use first 16 chars of UUID
    verts_shm_name = f"{prefix}sp_v_{uid}"
    edges_shm_name = f"{prefix}sp_e_{uid}"
    rotations_shm_name = f"{prefix}sp_r_{uid}"
    scales_shm_name = f"{prefix}sp_s_{uid}"
    offsets_shm_name = f"{prefix}sp_o_{uid}"

    verts_shm = shared_memory.SharedMemory(create=True, size=verts_size, name=verts_shm_name)
    edges_shm = shared_memory.SharedMemory(create=True, size=edges_size, name=edges_shm_name)
    rotations_shm = shared_memory.SharedMemory(create=True, size=rotations_size, name=rotations_shm_name)
    scales_shm = shared_memory.SharedMemory(create=True, size=scales_size, name=scales_shm_name)
    offsets_shm = shared_memory.SharedMemory(create=True, size=offsets_size, name=offsets_shm_name)

    cdef cnp.ndarray all_verts = np.ndarray((verts_size // 4,), dtype=np.float32, buffer=verts_shm.buf)
    cdef cnp.ndarray all_edges = np.ndarray((edges_size // 4,), dtype=np.uint32, buffer=edges_shm.buf)
    cdef cnp.ndarray rotations = np.ndarray((rotations_size // 4,), dtype=np.float32, buffer=rotations_shm.buf)
    cdef cnp.ndarray scales = np.ndarray((scales_size // 4,), dtype=np.float32, buffer=scales_shm.buf)
    cdef cnp.ndarray offsets = np.ndarray((offsets_size // 4,), dtype=np.float32, buffer=offsets_shm.buf)
    # Build counts without generators to avoid closures
    cdef list vert_counts_list = []
    cdef list edge_counts_list = []
    cdef list object_counts_list = []
    cdef list group
    cdef object obj
    cdef object eval_obj
    cdef object eval_mesh
    for group in mesh_groups:
        object_counts_list.append(len(group))
        for obj in group:
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.data
            vert_counts_list.append(len(eval_mesh.vertices))
            edge_counts_list.append(len(eval_mesh.edges))
    cdef cnp.ndarray vert_counts = np.array(vert_counts_list, dtype=np.uint32)
    cdef cnp.ndarray edge_counts = np.array(edge_counts_list, dtype=np.uint32)
    cdef cnp.ndarray object_counts = np.array(object_counts_list, dtype=np.uint32)

    cdef size_t idx_rot = 0
    cdef size_t idx_scale = 0
    cdef size_t idx_offset = 0
    cdef uint32_t curr_verts_offset = 0
    cdef uint32_t curr_edges_offset = 0
    cdef object quat
    cdef object scale_vec
    cdef object mesh
    cdef object pivot_obj
    cdef object pivot_matrix_world
    cdef object pivot_matrix_inv
    cdef object obj_local_matrix
    cdef object local_translation
    cdef object trans_vec
    cdef uint32_t obj_vert_count
    cdef uint32_t obj_edge_count
    cdef uint32_t vert_offset
    cdef uint32_t edge_offset
    cdef size_t group_idx = 0

    for group in mesh_groups:
        vert_offset = 0
        edge_offset = 0
        if is_group_mode:
            pivot_obj = pivots[group_idx]
            pivot_matrix_world = pivot_obj.matrix_world.copy()
            try:
                pivot_matrix_inv = pivot_matrix_world.inverted()
            except Exception:
                pivot_matrix_inv = Matrix.Identity(4)
            pivot_basis_inv = pivot_matrix_inv.to_3x3()
            use_pivot_transform = True
        else:
            pivot_obj = None
            pivot_matrix_inv = Matrix.Identity(4)
            pivot_basis_inv = Matrix.Identity(3)
            use_pivot_transform = False
        for obj in group:
            if use_pivot_transform:
                obj_local_matrix = pivot_matrix_inv @ obj.matrix_world
                quat = obj_local_matrix.to_3x3().to_quaternion()
                trans_vec = obj.matrix_world.translation - pivot_obj.matrix_world.translation
                local_translation = pivot_basis_inv @ trans_vec
            else:
                quat = obj.matrix_world.to_3x3().to_quaternion()
                local_translation = Vector((0.0, 0.0, 0.0))
            rotations[idx_rot] = quat.w
            rotations[idx_rot + 1] = quat.x
            rotations[idx_rot + 2] = quat.y
            rotations[idx_rot + 3] = quat.z
            idx_rot += 4

            scale_vec = obj.matrix_world.to_3x3().to_scale()
            scales[idx_scale] = scale_vec.x
            scales[idx_scale + 1] = scale_vec.y
            scales[idx_scale + 2] = scale_vec.z
            idx_scale += 3

            # Offset relative to the pivot coordinate system, accounting for child/parent hierarchy

            offsets[idx_offset] = local_translation.x
            offsets[idx_offset + 1] = local_translation.y
            offsets[idx_offset + 2] = local_translation.z
            idx_offset += 3

            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.data
            obj_vert_count = len(mesh.vertices)
            obj_edge_count = len(mesh.edges)

            if obj_vert_count > 0:
                mesh.vertices.foreach_get("co", all_verts[curr_verts_offset + vert_offset:curr_verts_offset + vert_offset + obj_vert_count * 3])
                vert_offset += obj_vert_count * 3

            if obj_edge_count > 0:
                mesh.edges.foreach_get("vertices", all_edges[curr_edges_offset + edge_offset:curr_edges_offset + edge_offset + obj_edge_count * 2])
                edge_offset += obj_edge_count * 2

        curr_verts_offset += vert_offset
        curr_edges_offset += edge_offset
        group_idx += 1

    cdef uint32_t[::1] vert_counts_mv = vert_counts
    cdef uint32_t[::1] edge_counts_mv = edge_counts
    cdef uint32_t[::1] object_counts_mv = object_counts

    shm_objects = (verts_shm, edges_shm, rotations_shm, scales_shm, offsets_shm)
    shm_names = (verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name)
    count_memory_views = (vert_counts_mv, edge_counts_mv, object_counts_mv)

    return shm_objects, shm_names, count_memory_views


def prepare_face_data(uint32_t total_objects, list mesh_groups):
    """Prepare face data for sending to engine after initial classification."""
    cdef uint32_t total_faces_count = 0
    cdef uint32_t total_face_vertices = 0
    cdef size_t expected_objects = 0
    cdef list group
    cdef object obj
    cdef uint32_t obj_face_count
    cdef uint32_t obj_vertex_count
    cdef cnp.ndarray[cnp.uint32_t, ndim=1] face_sizes_slice
    cdef cnp.ndarray[cnp.uint32_t, ndim=1] shm_face_sizes_buf = None
    cdef cnp.ndarray[cnp.uint32_t, ndim=1] shm_faces_buf = None
    cdef cnp.ndarray[cnp.uint32_t, ndim=1] face_counts = None
    cdef cnp.ndarray[cnp.uint32_t, ndim=1] face_vert_counts = None
    cdef uint32_t[::1] face_sizes_slice_view
    cdef uint32_t[::1] face_counts_mv
    cdef uint32_t[::1] face_sizes_mv
    cdef uint32_t[::1] face_vert_counts_mv
    cdef uint32_t[::1] face_vert_counts_view
    cdef uint32_t face_sizes_offset = 0
    cdef uint32_t obj_idx = 0
    cdef uint32_t faces_offset = 0
    cdef size_t faces_size = 0
    cdef tuple shm_objects
    cdef tuple shm_names
    cdef str faces_shm_name = ""
    cdef str face_sizes_shm_name = ""
    cdef object faces_shm = None
    cdef object face_sizes_shm = None
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # First pass: gather totals and validate counts
    for group in mesh_groups:
        expected_objects += len(group)
        for obj in group:
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.data
            total_faces_count += len(eval_mesh.polygons)

    if expected_objects != total_objects:
        raise ValueError(f"prepare_face_data: expected {expected_objects} objects, received {total_objects}")

    # Early exit when no faces are present
    if total_faces_count == 0:
        face_counts = np.zeros(total_objects, dtype=np.uint32)
        face_vert_counts = np.zeros(total_objects, dtype=np.uint32)
        shm_face_sizes_buf = np.zeros(0, dtype=np.uint32)

        face_counts_mv = face_counts
        face_sizes_mv = shm_face_sizes_buf
        face_vert_counts_mv = face_vert_counts

        return (), ("", ""), face_counts_mv, face_sizes_mv, face_vert_counts_mv, 0, 0

    cdef size_t face_sizes_size = <size_t>total_faces_count * 4

    # Platform-aware shared memory names
    # POSIX (macOS, Linux): Use leading '/' for namespace isolation
    # Windows: No leading '/'
    is_windows = platform.system() == "Windows"
    prefix = "" if is_windows else "/"
    uid_faces = uuid.uuid4().hex[:16]
    face_sizes_shm_name = f"{prefix}sp_fs_{uid_faces}"

    try:
        face_sizes_shm = shared_memory.SharedMemory(create=True, size=face_sizes_size, name=face_sizes_shm_name)
        shm_face_sizes_buf = np.ndarray((total_faces_count,), dtype=np.uint32, buffer=face_sizes_shm.buf)

        face_counts = np.empty(total_objects, dtype=np.uint32)
        face_vert_counts = np.empty(total_objects, dtype=np.uint32)

        face_sizes_offset = 0
        obj_idx = 0

        for group in mesh_groups:
            for obj in group:
                eval_obj = obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.data
                obj_face_count = <uint32_t>len(eval_mesh.polygons)
                face_counts[obj_idx] = obj_face_count

                if obj_face_count > 0:
                    face_sizes_slice = shm_face_sizes_buf[face_sizes_offset:face_sizes_offset + obj_face_count]
                    eval_mesh.polygons.foreach_get('loop_total', face_sizes_slice)

                    obj_vertex_count = 0
                    face_sizes_slice_view = face_sizes_slice
                    for i in range(obj_face_count):
                        obj_vertex_count += face_sizes_slice_view[i]

                    face_vert_counts[obj_idx] = obj_vertex_count
                    total_face_vertices += obj_vertex_count
                else:
                    face_vert_counts[obj_idx] = 0

                face_sizes_offset += obj_face_count
                obj_idx += 1

        if total_face_vertices == 0:
            raise ValueError("prepare_face_data: collected faces but no vertex indices recorded")

        faces_shm_name = f"{prefix}sp_f_{uid_faces}"
        faces_size = <size_t>total_face_vertices * 4
        faces_shm = shared_memory.SharedMemory(create=True, size=faces_size, name=faces_shm_name)
        shm_faces_buf = np.ndarray((total_face_vertices,), dtype=np.uint32, buffer=faces_shm.buf)

        faces_offset = 0
        obj_idx = 0
        face_vert_counts_view = face_vert_counts

        for group in mesh_groups:
            for obj in group:
                eval_obj = obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.data
                obj_vertex_count = face_vert_counts_view[obj_idx]
                if obj_vertex_count > 0:
                    eval_mesh.polygons.foreach_get("vertices", shm_faces_buf[faces_offset:faces_offset + obj_vertex_count])
                    faces_offset += obj_vertex_count
                obj_idx += 1

        face_counts_mv = face_counts
        face_sizes_mv = shm_face_sizes_buf
        face_vert_counts_mv = face_vert_counts_view

        shm_objects = (faces_shm, face_sizes_shm)
        shm_names = (faces_shm_name, face_sizes_shm_name)

        return shm_objects, shm_names, face_counts_mv, face_sizes_mv, face_vert_counts_mv, total_faces_count, total_face_vertices

    except Exception:
        if faces_shm is not None:
            try:
                pass
            except Exception:
                pass
            faces_shm.close()
            faces_shm.unlink()
        if face_sizes_shm is not None:
            try:
                pass
            except Exception:
                pass
            face_sizes_shm.close()
            face_sizes_shm.unlink()
        raise
