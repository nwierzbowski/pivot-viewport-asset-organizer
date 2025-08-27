#pragma once

#include "util.h"

#include <unordered_map>
#include <vector>

struct VoxelKey {
    int32_t x, y, z;
    bool operator==(const VoxelKey& o) const noexcept {
        return x==o.x && y==o.y && z==o.z;
    }

    VoxelKey operator+(const Vec3i& other) const {
        return {x + other.x, y + other.y, z + other.z};
    }
};

struct VoxelKeyHash {
    size_t operator()(const VoxelKey& k) const noexcept {
        return (size_t)k.x * 73856093u ^ (size_t)k.y * 19349663u ^ (size_t)k.z * 83492791u;
    }
};

inline VoxelKey make_voxel_key(const Vec3& p, float voxelSize) {
    return {
        (int32_t)std::floor(p.x / voxelSize),
        (int32_t)std::floor(p.y / voxelSize),
        (int32_t)std::floor(p.z / voxelSize)
    };
}

struct VoxelData
{
    std::vector<uint32_t> vertex_indices;
    Vec3 facing;
    Vec3 dir;
};

using VoxelMap = std::unordered_map<VoxelKey, VoxelData, VoxelKeyHash>;

VoxelMap build_voxel_map(const Vec3 *verts, uint32_t vertCount, float voxelSize);

void calculate_voxel_map_stats(VoxelMap &voxel_map,
                               const Vec3 *norms, const Vec3 *verts, std::vector<VoxelKey> &wire_guesses);