#include "wire_detect.h"
#include "vec.h"
#include "voxel.h"

#include <vector>
#include <algorithm>
#include <cstdint>
#include <queue>

// Function to find the median of a vector
double find_median(std::vector<uint32_t> &data)
{
    size_t n = data.size();
    if (n % 2 == 1)
    {
        return static_cast<double>(data[n / 2]);
    }
    else
    {
        return (static_cast<double>(data[n / 2 - 1]) + data[n / 2]) / 2.0;
    }
}

// Function to exclude outliers using the IQR method
std::vector<uint32_t> exclude_outliers_iqr(std::vector<uint32_t> data)
{
    // Sort the data to find quartiles
    std::sort(data.begin(), data.end());

    size_t n = data.size();
    if (n < 4)
        return data; // Not enough data to reliably find quartiles

    // Find Q1 and Q3
    std::vector<uint32_t> lower_half(data.begin(), data.begin() + n / 2);
    std::vector<uint32_t> upper_half(data.begin() + (n + 1) / 2, data.end());

    double q1 = find_median(lower_half);
    double q3 = find_median(upper_half);

    double iqr = q3 - q1;
    double lower_bound = q1 - 1.5 * iqr;
    double upper_bound = q3 + 1.5 * iqr;

    // Use a temporary vector to store the non-outliers
    std::vector<uint32_t> filtered_data;
    for (uint32_t val : data)
    {
        if (val >= lower_bound && val <= upper_bound)
        {
            filtered_data.push_back(val);
        }
    }
    return filtered_data;
}

std::vector<char> select_wire_verts(const Vec3 *verts,
                                    const Vec3 *vert_norms,
                                    uint32_t vertCount,
                                    const std::vector<std::vector<uint32_t>> &adj_verts,
                                    const std::vector<VoxelKey> &voxel_guesses,
                                    VoxelMap &voxel_map)
{
    if (!verts || vertCount == 0 || !vert_norms ||
        adj_verts.empty() || voxel_map.empty() || voxel_guesses.empty())
        return std::vector<char>(vertCount, false);

    std::vector<uint32_t> vertex_guess_indices;
    vertex_guess_indices.reserve(voxel_guesses.size() * 4);

    uint32_t guessed_vertex_count = 0;
    for (const VoxelKey &vg : voxel_guesses)
        guessed_vertex_count += voxel_map.at(vg).vertex_indices.size();

    std::vector<uint32_t> neighbor_sizes;
    std::vector<char> is_wire(vertCount, false);
    std::vector<char> in_guess(vertCount, false);

    if (guessed_vertex_count < vertCount / 6)
    {
        std::vector<char> neighbor_mark(vertCount, false);
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
        is_wire[idx] = true;

    // Boundary extraction
    std::vector<uint32_t> boundaries;
    boundaries.reserve(vertex_guess_indices.size() * 2);
    std::vector<char> is_boundary(vertCount, false);

    for (uint32_t idx : vertex_guess_indices)
        for (uint32_t nb : adj_verts[idx])
            if (!is_wire[nb] && !is_boundary[nb])
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
                if (!is_wire[nb])
                {
                    is_wire[nb] = true;
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

    return is_wire;
}