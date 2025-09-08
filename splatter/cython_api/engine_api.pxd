from libc.stdint cimport uint32_t
from splatter.cython_api.vec_api cimport Vec3, uVec2i
from splatter.cython_api.quaternion_api cimport Quaternion

cdef extern from "../engine/engine.h" nogil:
    void prepare_object_batch(const Vec3 *verts_flat, const uVec2i *edges_flat, const uint32_t *vert_counts, const uint32_t *edge_counts, uint32_t num_objects, Quaternion *out_rots, Vec3 *out_trans)
    void group_objects(Vec3 *verts_flat, uVec2i *edges_flat, const uint32_t *vert_counts, const uint32_t *edge_counts, const Vec3 *offsets, const Quaternion *rotations, uint32_t num_objects);

    void apply_rotation(Vec3* verts, uint32_t vertCount, const Quaternion &rotation);