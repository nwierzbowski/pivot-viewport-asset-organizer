#include "wire_detect.h"

#include "object/computation/voxel.h"
#include "share/stats.h"

#include <vector>
#include <cstdint>
#include <queue>
#include <iostream>
#include <unordered_set>

std::vector<VoxelKey> guess_wire_voxels(VoxelMap &voxel_map)
{
    constexpr std::array<Vec3i, 6> neighbor_dirs = {{{0, 0, 1}, {0, 1, 0}, {1, 0, 0}, {0, 0, -1}, {0, -1, 0}, {-1, 0, 0}}};

    std::vector<VoxelKey> wire_guesses;

    for (auto &[voxel_coord, voxel_data] : voxel_map)
    {

        uint8_t neighbors = 0;
        for (const auto &d : neighbor_dirs)
            if (voxel_map.find(voxel_coord + d) != voxel_map.end())
                neighbors++;

        float sum_lambda = voxel_data.lambda1 + voxel_data.lambda2;
        if (voxel_data.avg_normal.length_squared() < 0.25f * 0.25f &&
            sum_lambda > 0.0f &&
            voxel_data.lambda1 > 0.85f * sum_lambda &&
            neighbors <= 4)
        {
            wire_guesses.push_back(voxel_coord);
        }
    }

    // Remove wire guesses that don't have at least one adjacent wire guess
    std::unordered_set<VoxelKey, VoxelKeyHash> wire_set(wire_guesses.begin(), wire_guesses.end());
    std::vector<VoxelKey> filtered_guesses;
    for (const VoxelKey &vg : wire_guesses)
    {
        bool has_adjacent_wire = false;
        for (const auto &d : neighbor_dirs)
        {
            VoxelKey neighbor = vg + d;
            if (wire_set.find(neighbor) != wire_set.end())
            {
                has_adjacent_wire = true;
                break;
            }
        }
        if (has_adjacent_wire)
        {
            filtered_guesses.push_back(vg);
        }
    }

    return filtered_guesses;
}

void select_wire_verts(
    uint32_t vertCount,
    const std::vector<std::vector<uint32_t>> &adj_verts,
    const std::vector<VoxelKey> &voxel_guesses,
    VoxelMap &voxel_map,
    std::vector<bool> &mask)
{
    if (vertCount == 0 ||
        adj_verts.empty() || voxel_map.empty() || voxel_guesses.empty())
        return;

    std::vector<uint32_t> vertex_guess_indices;
    vertex_guess_indices.reserve(voxel_guesses.size() * 4);
    uint32_t guessed_vertex_count = 0;
    for (const VoxelKey &vg : voxel_guesses)
        guessed_vertex_count += voxel_map.at(vg).vertex_indices.size();

    std::vector<uint32_t> neighbor_sizes;

    std::vector<bool> in_guess(vertCount, false);

    if (guessed_vertex_count < vertCount / 6)
    {
        std::vector<bool> neighbor_mark(vertCount, false);
        for (const VoxelKey &vg : voxel_guesses)
        {
            uint32_t neighbor_count = 0;
            const auto &vIdxs = voxel_map.at(vg).vertex_indices;
            for (uint32_t idx : vIdxs)
            {
                vertex_guess_indices.push_back(idx);
                if (!in_guess[idx])
                    in_guess[idx] = true;
                for (uint32_t nb : adj_verts[idx])
                {
                    if (!in_guess[nb] && !neighbor_mark[nb])
                    {
                        neighbor_mark[nb] = true;
                        neighbor_count++;
                    }
                }
            }
            neighbor_sizes.push_back(neighbor_count);
        }
    }

    // Print vertex guess indices
    std::cout << "Vertex guess indices: ";
    for (uint32_t idx : vertex_guess_indices)
        std::cout << idx << " ";
    std::cout << std::endl;

    float density = 0.f;
    if (!neighbor_sizes.empty())
    {
        auto filtered = exclude_outliers_iqr(neighbor_sizes);
        if (!filtered.empty())
        {
            for (uint32_t s : filtered)
                density += static_cast<float>(s);
            density /= static_cast<float>(filtered.size());
        }
    }

    for (uint32_t idx : vertex_guess_indices)
        mask[idx] = true;

    // Boundary extraction
    std::vector<uint32_t> boundaries;
    boundaries.reserve(vertex_guess_indices.size() * 2);
    std::vector<char> is_boundary(vertCount, false);

    for (uint32_t idx : vertex_guess_indices)
        for (uint32_t nb : adj_verts[idx])
            if (!mask[nb] && !is_boundary[nb])
            {
                is_boundary[nb] = true;
                boundaries.push_back(nb);
            }

    // Split boundaries into groups (BFS)
    std::vector<char> visited(vertCount, false);
    std::vector<std::vector<uint32_t>> groups;
    groups.reserve(boundaries.size() / 8 + 1);

    for (uint32_t seed : boundaries)
    {
        if (visited[seed])
            continue;
        std::vector<uint32_t> group;
        std::queue<uint32_t> q;
        q.push(seed);
        visited[seed] = true;
        while (!q.empty())
        {
            auto cur = q.front();
            q.pop();
            group.push_back(cur);
            for (uint32_t nb : adj_verts[cur])
                if (is_boundary[nb] && !visited[nb])
                {
                    visited[nb] = true;
                    q.push(nb);
                }
        }
        groups.push_back(std::move(group));
    }

    float limit = density * 0.4f;
    for (auto &g : groups)
    {
        std::queue<uint32_t> frontier;
        for (uint32_t v : g)
            frontier.push(v);
        std::queue<uint32_t> next;
        while (!frontier.empty())
        {
            uint32_t cur = frontier.front();
            frontier.pop();
            for (uint32_t nb : adj_verts[cur])
                if (!mask[nb])
                {
                    mask[nb] = true;
                    next.push(nb);
                    if (next.size() > limit)
                    {
                        while (!next.empty())
                            next.pop();
                        frontier = std::queue<uint32_t>(); // clear
                        break;
                    }
                }
            if (frontier.empty())
                std::swap(frontier, next);
        }
    }
}