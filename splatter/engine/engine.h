#pragma once

#include "share/vec.h"
void prepare_object_batch(const Vec3 *verts_flat, const uVec2i *edges_flat, const uint32_t *vert_counts, const uint32_t *edge_counts, uint32_t num_objects, Vec3 *out_rots, Vec3 *out_trans);
void group_objects(Vec3 *verts_flat, uVec2i *edges_flat, const uint32_t *vert_counts, const uint32_t *edge_counts, const Vec3 *offsets, const Vec3 *rotations, uint32_t num_objects);