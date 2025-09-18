#pragma once

#include "share/vec.h"
#include "share/quaternion.h"

#include <cstdint>
#include <span>

void prepare_object_batch(std::span<const Vec3> verts_flat, std::span<const uVec2i> edges_flat, std::span<const uint32_t> vert_counts, std::span<const uint32_t> edge_counts, std::span<Quaternion> out_rots, std::span<Vec3> out_trans);

void group_objects(std::span<Vec3> verts_flat, std::span<uVec2i> edges_flat, std::span<const uint32_t> vert_counts, std::span<const uint32_t> edge_counts, std::span<const Vec3> offsets, std::span<const Quaternion> rotations, std::span<const Vec3> scales);

void apply_rotation(Vec3* verts, uint32_t vertCount, const Quaternion &rotation);