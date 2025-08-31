#include "analysis.h"
#include "vec.h"
#include "geo2d.h"

#include <vector>
#include <cstdint>
#include <unordered_set>

#include <chrono>
#include <iostream>

std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3> &verts, BoundingBox3D full_box)
{
    return convex_hull_2D(verts, &Vec3::z, full_box.min_corner.z, full_box.min_corner.z + 0.001);
}

float calc_ratio_full_to_base(const BoundingBox2D &full_box, const BoundingBox2D &base_box)
{
    if (base_box.area == 0)
        return 0;
    return full_box.area / base_box.area;
}

struct Slice
{
    std::vector<uint32_t> vert_indices;
    std::vector<std::vector<Vec2>> chulls;
    float z_upper;
    float z_lower;
    Vec2 cog;
    float area;
};

static inline void build_slice_island_hulls(
    Slice &s,
    const Vec3* verts,
    uint32_t vertCount,
    const std::vector<std::vector<uint32_t>> &adj_verts)
{
    if (s.vert_indices.empty())
        return;

    // Ensure output is only from this invocation
    s.chulls.clear();
    // Rough heuristic reserve (most slices have few islands)
    s.chulls.reserve(std::min<size_t>(8, s.vert_indices.size()));

    // Mark which vertices belong to this slice (O(|slice|))
    std::vector<uint8_t> in_slice(vertCount, 0);
    for (uint32_t vi : s.vert_indices)
        in_slice[vi] = 1;

    // Visited flags only for vertices in slice
    std::vector<uint8_t> visited(vertCount, 0);

    // Reusable buffers
    std::vector<uint32_t> stack;
    stack.reserve(128);

    std::vector<uint32_t> island_indices;
    island_indices.reserve(256);

    std::vector<Vec3> island_verts;
    island_verts.reserve(256);

    for (uint32_t seed : s.vert_indices)
    {
        if (visited[seed]) continue;

        // Start new island
        stack.clear();
        island_indices.clear();
        stack.push_back(seed);
        visited[seed] = 1;

        while (!stack.empty())
        {
            uint32_t v = stack.back();
            stack.pop_back();
            island_indices.push_back(v);

            const auto &nbrs = adj_verts[v];
            for (uint32_t n : nbrs)
            {
                if (!in_slice[n] || visited[n]) continue;
                visited[n] = 1;
                stack.push_back(n);
            }
        }

        // Build verts array for hull (copy unavoidable unless hull API extended)
        island_verts.clear();
        island_verts.reserve(island_indices.size());
        for (uint32_t vi : island_indices)
            island_verts.push_back(verts[vi]);

        auto hull = convex_hull_2D(island_verts, &Vec3::z, s.z_lower, s.z_upper);
        if (!hull.empty())
            s.chulls.push_back(std::move(hull));
    }
}

struct PolyData {
    Vec2 cog;
    float area;
};

PolyData calc_cog_area(const std::vector<Vec2>& vertices) {
    Vec2 centroid = {0.0, 0.0};
    float signedArea = 0.0;

    // A polygon must have at least 3 vertices
    if (vertices.size() < 3) {
        // Handle degenerate cases, e.g., return {0,0} or throw an exception
        return {{0,0}, 0.0};
    }

    for (size_t i = 0; i < vertices.size(); ++i) {
        Vec2 p0 = vertices[i];
        // The next point wraps around to the first for the last vertex
        Vec2 p1 = vertices[(i + 1) % vertices.size()];

        double crossProductTerm = (p0.x * p1.y) - (p1.x * p0.y);
        signedArea += crossProductTerm;
        centroid.x += (p0.x + p1.x) * crossProductTerm;
        centroid.y += (p0.y + p1.y) * crossProductTerm;
    }

    signedArea *= 0.5;

    // Handle cases where the polygon has zero area (e.g., collinear points)
    if (std::fabs(signedArea) < 1e-9) { // Use a small epsilon for float comparison
        // Polygon is degenerate (e.g., a line segment).
        // The centroid is ill-defined by area.
        // A common approach is to return the average of the vertices
        // or a specific error indicator.
        if (!vertices.empty()) {
            Vec2 avg_centroid = {0.0, 0.0};
            for (const auto& p : vertices) {
                avg_centroid.x += p.x;
                avg_centroid.y += p.y;
            }
            avg_centroid.x /= vertices.size();
            avg_centroid.y /= vertices.size();
            return {avg_centroid, std::fabs(signedArea)};
        }
        return {{0,0}, 0.0}; // Default for empty or truly degenerate
    }

    centroid.x /= (6.0 * signedArea);
    centroid.y /= (6.0 * signedArea);

    return {centroid, std::fabs(signedArea)};
}


Vec3 calc_cog_volume(const Vec3* verts, uint32_t vertCount, const std::vector<std::vector<uint32_t>> &adj_verts, BoundingBox3D full_box)
{
    const float slice_height = .01f;
    const uint8_t slice_count = static_cast<uint8_t>((full_box.max_corner.z - full_box.min_corner.z) / slice_height);


    std::vector<Slice> slices(slice_count);
    auto start = std::chrono::high_resolution_clock::now();
    // Init slices
    for (uint8_t i = 0; i < slice_count; ++i)
    {
        slices[i].z_upper = full_box.min_corner.z + (i + 1) * slice_height;
        slices[i].z_lower = full_box.min_corner.z + i * slice_height;
        slices[i].vert_indices.reserve(vertCount / slice_count);
    }
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);
    std::cout << "init slices: " << (float) duration.count() / 1000000 << " ms" << std::endl;

    start = std::chrono::high_resolution_clock::now();
    // Distribute vertices into slices
    for (uint32_t i = 0; i < vertCount; i++)
    {
        const Vec3 &v = verts[i];
        float rel = (v.z - full_box.min_corner.z) / slice_height;
        // Clamp to last slice to avoid out-of-range when v.z == max_corner.z
        uint32_t idx = static_cast<uint32_t>(rel);
        if (idx >= slice_count) idx = slice_count - 1;
        uint8_t slice_index = static_cast<uint8_t>(idx);
        slices[slice_index].vert_indices.push_back(i);
    }
    end = std::chrono::high_resolution_clock::now();
    duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);
    std::cout << "Distribute vertices: " << (float) duration.count() / 1000000 << " ms" << std::endl;

    start = std::chrono::high_resolution_clock::now();
    // Calculate convex hulls for the connected islands in each slice
    long long total_build_time = 0;
    long long total_avg_time = 0;
    for (Slice &s : slices)
    {
        auto loop_start = std::chrono::high_resolution_clock::now();
        build_slice_island_hulls(s, verts, vertCount, adj_verts);
        auto build_end = std::chrono::high_resolution_clock::now();
        total_build_time += std::chrono::duration_cast<std::chrono::nanoseconds>(build_end - loop_start).count();

        auto avg_start = std::chrono::high_resolution_clock::now();
        //Average the cog weighted by area
        Vec2 weighted_cog_sum = {0.0f, 0.0f};
        float total_area = 0.0f;

        for (const std::vector<Vec2> &hull : s.chulls)
        {
            PolyData pd = calc_cog_area(hull);
            weighted_cog_sum.x += pd.cog.x * pd.area;
            weighted_cog_sum.y += pd.cog.y * pd.area;
            total_area += pd.area;
        }

        if (total_area > 0.0f)
        {
            weighted_cog_sum.x /= total_area;
            weighted_cog_sum.y /= total_area;
        }

        s.cog = weighted_cog_sum;
        s.area = total_area;
        auto avg_end = std::chrono::high_resolution_clock::now();
        total_avg_time += std::chrono::duration_cast<std::chrono::nanoseconds>(avg_end - avg_start).count();
    }
    end = std::chrono::high_resolution_clock::now();
    duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);
    std::cout << "Total build_slice_island_hulls time: " << (float) total_build_time / 1000000 << " ms" << std::endl;
    std::cout << "Total averaging time: " << (float) total_avg_time / 1000000 << " ms" << std::endl;
    std::cout << "Calculate convex hulls: " << (float) duration.count() / 1000000 << " ms" << std::endl;
    

    start = std::chrono::high_resolution_clock::now();
    //Average the cog of each slice weighted by their areas
    Vec3 overall_cog = {0.0f, 0.0f, 0.0f};
    float total_area = 0.0f;

    for (const Slice &s : slices)
    {
        overall_cog.x += s.cog.x * s.area;
        overall_cog.y += s.cog.y * s.area;
        overall_cog.z += (s.z_lower + s.z_upper) * 0.5f * s.area;
        total_area += s.area;
    }

    if (total_area > 0.0f)
    {
        overall_cog.x /= total_area;
        overall_cog.y /= total_area;
        overall_cog.z /= total_area;
    }
    end = std::chrono::high_resolution_clock::now();
    duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);
    std::cout << "Average COG: " << (float) duration.count() / 1000000 << " ms" << std::endl;

    return overall_cog;
}