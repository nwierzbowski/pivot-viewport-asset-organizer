#pragma once

#include "object/computation/voxel.h"

#include <vector>

void select_wire_verts(
    uint32_t vertCount,
    const std::vector<std::vector<uint32_t>> &adj_verts,
    const std::vector<VoxelKey> &voxel_guesses,
    VoxelMap &voxel_map,
    std::vector<bool> &mask);

std::vector<VoxelKey> guess_wire_voxels(VoxelMap &voxel_map);