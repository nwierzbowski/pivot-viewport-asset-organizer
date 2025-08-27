#include "voxel.h"
#include "util.h"
#include "linalg3.h"

#include <vector>
#include <unordered_map>

VoxelMap
build_voxel_map(const Vec3 *verts, uint32_t vertCount,
                float voxelSize)
{
    VoxelMap voxel_map;
    if (!verts || vertCount == 0)
        return voxel_map;

    voxel_map.reserve(vertCount / 4 + 1);

    for (uint32_t i = 0; i < vertCount; ++i)
    {
        VoxelKey key = make_voxel_key(verts[i], voxelSize);
        voxel_map[key].vertex_indices.push_back(i);
    }
    return voxel_map;
}

void calculate_voxel_map_stats(VoxelMap &voxel_map,
                               const Vec3 *norms, const Vec3 *verts, std::vector<VoxelKey> &wire_guesses)
{
    constexpr std::array<Vec3i, 6> neighbor_dirs = {{{0, 0, 1}, {0, 1, 0}, {1, 0, 0}, {0, 0, -1}, {0, -1, 0}, {-1, 0, 0}}};
    wire_guesses.reserve(wire_guesses.size() + voxel_map.size() / 16 + 4);

    for (auto &[voxel_coord, voxel_data] : voxel_map)
    {
        const size_t cnt = voxel_data.vertex_indices.size();
        if (cnt == 0)
            continue;

        Vec3 avg_facing{0, 0, 0};
        for (uint32_t i : voxel_data.vertex_indices)
            avg_facing = avg_facing + norms[i];
        avg_facing = avg_facing / static_cast<float>(cnt);

        float lambda1 = 0.f, lambda2 = 0.f;
        Vec3 prim_vec{0, 0, 0}, sec_vec{0, 0, 0};

        if (cnt >= 3)
        {
            float cov[3][3];
            compute_cov(voxel_data.vertex_indices, verts, cov);
            eig3(cov, lambda1, lambda2, prim_vec, sec_vec);
        }

        voxel_data.facing = avg_facing;
        voxel_data.dir = prim_vec;

        uint8_t neighbors = 0;
        for (const auto &d : neighbor_dirs)
            if (voxel_map.find(voxel_coord + d) != voxel_map.end())
                neighbors++;

        float facing_len_sq = avg_facing.x * avg_facing.x + avg_facing.y * avg_facing.y + avg_facing.z * avg_facing.z;
        float sum_lambda = lambda1 + lambda2;
        if (facing_len_sq < 0.25f * 0.25f &&
            sum_lambda > 0.f &&
            lambda1 > 0.9f * sum_lambda &&
            neighbors <= 3)
        {
            wire_guesses.push_back(voxel_coord);
        }
    }
}