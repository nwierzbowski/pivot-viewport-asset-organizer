#pragma once

#include "share/vec.h"

#include <cmath>
#include <unordered_map>
#include <vector>
#include <span>

struct VoxelKey
{
    int32_t x, y, z;
    bool operator==(const VoxelKey &o) const noexcept
    {
        return x == o.x && y == o.y && z == o.z;
    }

    VoxelKey operator+(const Vec3i &other) const
    {
        return {x + other.x, y + other.y, z + other.z};
    }
};

struct VoxelKeyHash
{
    size_t operator()(const VoxelKey &k) const noexcept
    {
        return (size_t)k.x * 73856093u ^ (size_t)k.y * 19349663u ^ (size_t)k.z * 83492791u;
    }
};

inline VoxelKey make_voxel_key(const Vec3 &p, float voxelSize)
{
    return {
        (int32_t)std::floor(p.x / voxelSize),
        (int32_t)std::floor(p.y / voxelSize),
        (int32_t)std::floor(p.z / voxelSize)};
}

struct VoxelData
{
    std::vector<uint32_t> vertex_indices;
    float projected_lambda1;
    float projected_lambda2;
    Vec2 projected_prim_vec;
    Vec2 projected_sec_vec;
    float lambda1;
    float lambda2;
    float lambda3;
    Vec3 prim_vec;
    Vec3 sec_vec;
    Vec3 third_vec;
    Vec3 centroid;
};

using VoxelMap = std::unordered_map<VoxelKey, VoxelData, VoxelKeyHash>;

VoxelMap build_voxel_map(std::span<const Vec3> verts, float voxelSize);