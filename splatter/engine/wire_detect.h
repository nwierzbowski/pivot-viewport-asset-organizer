#pragma once

#include "util.h"
#include "voxel.h"

#include <vector>
#include <unordered_map>

std::vector<char> select_wire_verts(const Vec3 *verts,
                                    const Vec3 *vert_norms,
                                    uint32_t vertCount,
                                    const std::vector<std::vector<uint32_t>> &adj_verts,
                                    const std::vector<VoxelKey> &voxel_guesses,
                                    VoxelMap &voxel_map);