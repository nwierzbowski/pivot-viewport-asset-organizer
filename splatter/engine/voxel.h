#pragma once

#include "util.h"

#include <unordered_map>
#include <vector>

struct Vec3Hash
{
    std::size_t operator()(const Vec3 &v) const
    {
        const std::size_t p1 = 73856093;
        const std::size_t p2 = 19349663;
        const std::size_t p3 = 83492791;

        return (static_cast<std::size_t>(v.x) * p1) ^
               (static_cast<std::size_t>(v.y) * p2) ^
               (static_cast<std::size_t>(v.z) * p3);
    }
};

struct VoxelData
{
    std::vector<uint32_t> vertex_indices;
    Vec3 facing;
    Vec3 dir;
};

std::unordered_map<Vec3, VoxelData, Vec3Hash>
build_voxel_map(const Vec3 *verts, uint32_t vertCount,
                float voxelSize);

void calculate_voxel_map_stats(std::unordered_map<Vec3, VoxelData, Vec3Hash> &voxel_map,
                               const Vec3 *norms, const Vec3 *verts, std::vector<Vec3> &wire_guesses);