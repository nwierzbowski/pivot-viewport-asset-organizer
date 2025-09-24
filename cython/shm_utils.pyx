import numpy as np
cimport numpy as cnp
import uuid
import multiprocessing.shared_memory as shared_memory
from libc.stdint cimport uint32_t
from libc.stddef cimport size_t


def create_data_arrays(uint32_t total_verts, uint32_t total_edges, uint32_t total_objects, list mesh_groups):
    cdef uint32_t num_groups = len(mesh_groups)
    verts_size = total_verts * 3 * 4  # float32 = 4 bytes
    edges_size = total_edges * 2 * 4  # uint32 = 4 bytes
    rotations_size = total_objects * 4 * 4  # float32 = 4 bytes
    scales_size = total_objects * 3 * 4
    offsets_size = total_objects * 3 * 4

    verts_shm_name = f"splatter_verts_{uuid.uuid4().hex}"
    edges_shm_name = f"splatter_edges_{uuid.uuid4().hex}"
    rotations_shm_name = f"splatter_rotations_{uuid.uuid4().hex}"
    scales_shm_name = f"splatter_scales_{uuid.uuid4().hex}"
    offsets_shm_name = f"splatter_offsets_{uuid.uuid4().hex}"

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
    for group in mesh_groups:
        object_counts_list.append(len(group))
        for obj in group:
            vert_counts_list.append(len(obj.data.vertices))
            edge_counts_list.append(len(obj.data.edges))
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
    cdef object trans_vec
    cdef object mesh
    cdef uint32_t obj_vert_count
    cdef uint32_t obj_edge_count
    cdef uint32_t vert_offset
    cdef uint32_t edge_offset
    cdef object ref_trans

    for group in mesh_groups:
        vert_offset = 0
        edge_offset = 0
        # Get reference position from first object in group
        ref_trans = group[0].matrix_world.translation if group else None
        for obj in group:
            quat = obj.matrix_world.to_3x3().to_quaternion()
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

            trans_vec = obj.matrix_world.translation
            # Calculate offset relative to first object in group
            if ref_trans is not None:
                offsets[idx_offset] = trans_vec.x - ref_trans.x
                offsets[idx_offset + 1] = trans_vec.y - ref_trans.y
                offsets[idx_offset + 2] = trans_vec.z - ref_trans.z
            else:
                offsets[idx_offset] = trans_vec.x
                offsets[idx_offset + 1] = trans_vec.y
                offsets[idx_offset + 2] = trans_vec.z
            idx_offset += 3

            mesh = obj.data
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

    cdef uint32_t[::1] vert_counts_mv = vert_counts
    cdef uint32_t[::1] edge_counts_mv = edge_counts
    cdef uint32_t[::1] object_counts_mv = object_counts

    shm_objects = (verts_shm, edges_shm, rotations_shm, scales_shm, offsets_shm)
    shm_names = (verts_shm_name, edges_shm_name, rotations_shm_name, scales_shm_name, offsets_shm_name)
    count_memory_views = (vert_counts_mv, edge_counts_mv, object_counts_mv)

    return shm_objects, shm_names, count_memory_views
