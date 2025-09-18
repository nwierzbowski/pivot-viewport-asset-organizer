#include "cog.h"

#include "share/vec.h"
#include "object/computation/b_box.h"
#include "object/computation/chull.h"

#include <vector>
#include <cstdint>
#include <algorithm>
#include <limits>
#include <span>

// Build per-slice edge buckets: slice_edges[slice_index] contains indices of edges overlapping slice slice_index.
static inline void bucket_edges_per_slice(
    std::vector<std::vector<uint32_t>> &slice_edges,
    std::span<const uVec2i> edges,
    const std::vector<float> &vert_z,
    float z0,
    float slice_height,
    float inv_slice_height,
    uint8_t slice_count)
{
    slice_edges.assign(slice_count, {});
    for (uint32_t edge_index = 0; edge_index < edges.size(); ++edge_index)
    {
        const uVec2i &edge = edges[edge_index];
        float z1 = vert_z[edge.x];
        float z2 = vert_z[edge.y];
        float edge_z_min = z1 < z2 ? z1 : z2;
        float edge_z_max = z1 > z2 ? z1 : z2;
        float slice_span_top = z0 + slice_height * slice_count;
        if (edge_z_max <= z0 || edge_z_min >= slice_span_top)
            continue;
        int first_slice = (int)std::ceil((edge_z_min - z0) * inv_slice_height);
        int last_slice = (int)std::floor((edge_z_max - z0) * inv_slice_height);
        if (first_slice > last_slice)
            continue;
        if (last_slice < 0 || first_slice >= slice_count)
            continue;
        if (first_slice < 0)
            first_slice = 0;
        if (last_slice >= slice_count)
            last_slice = slice_count - 1;
        for (int slice_index = first_slice; slice_index <= last_slice; ++slice_index)
            slice_edges[slice_index].push_back(edge_index);
    }
}

// Build slice islands and directly compute aggregated area and COG (avoids storing hulls)
static inline void build_slice_islands(
    const std::vector<Vec2> &vert_xy,
    const std::vector<float> &vert_z,
    std::span<const uVec2i> edges,
    const std::vector<uint32_t> &slice_edge_indices,
    float z_lower,
    float z_upper,
    const std::vector<uint32_t> &slice_verts,
    const std::vector<uint32_t> &vertex_comp,
    const std::vector<uint32_t> &cid_to_index,
    uint32_t num_components,
    Vec2 &out_cog,
    float &out_area,
    BoundingBox2D &out_box)
{
    out_cog = {0.f, 0.f};
    out_area = 0.f;
    out_box = BoundingBox2D{};
    out_box.area = 0.f; // Initialize to 0 for empty case
    float min_x = std::numeric_limits<float>::max();
    float max_x = std::numeric_limits<float>::lowest();
    float min_y = std::numeric_limits<float>::max();
    float max_y = std::numeric_limits<float>::lowest();
    bool has_points = false;
    if (slice_edge_indices.empty())
        return;
    const float EPS = 1e-8f;

    // Generation-based reuse (static, not thread-safe)
    static std::vector<std::vector<Vec2>> comp_points;
    static std::vector<uint32_t> comp_gen;
    static uint32_t global_gen = 1;
    if (comp_points.size() < num_components)
    {
        comp_points.resize(num_components);
        comp_gen.resize(num_components, 0);
    }
    global_gen++;
    if (global_gen == 0)
    { // wraparound safeguard
        std::fill(comp_gen.begin(), comp_gen.end(), 0);
        global_gen = 1;
    }
    std::vector<uint32_t> active;
    active.reserve(32);

    auto ensure_active = [&](uint32_t component_index)
    {
        if (comp_gen[component_index] != global_gen)
        {
            comp_points[component_index].clear();
            comp_gen[component_index] = global_gen;
            active.push_back(component_index);
        }
    };

    // Add vertex points within the slice
    for (uint32_t vertex_id : slice_verts)
    {
        uint32_t component_index = cid_to_index[vertex_comp[vertex_id]];
        ensure_active(component_index);
        comp_points[component_index].push_back(vert_xy[vertex_id]);
    }
    // Add edge intersection points with the slice planes
    for (uint32_t edge_index : slice_edge_indices)
    {
        const uVec2i &edge = edges[edge_index];
        float z1 = vert_z[edge.x];
        float z2 = vert_z[edge.y];
        float z_diff = z2 - z1;
        if (std::abs(z_diff) < 1e-8f)
            continue;
        uint32_t component_index = cid_to_index[vertex_comp[edge.x]];
        bool z1_inside = (z1 >= z_lower - EPS && z1 <= z_upper + EPS);
        bool z2_inside = (z2 >= z_lower - EPS && z2 <= z_upper + EPS);
        auto add_interp = [&](float t)
        {
            ensure_active(component_index);
            const Vec2 &A_xy = vert_xy[edge.x];
            const Vec2 &B_xy = vert_xy[edge.y];
            comp_points[component_index].push_back({A_xy.x + (B_xy.x - A_xy.x) * t, A_xy.y + (B_xy.y - A_xy.y) * t});
        };
        if (!z1_inside && !z2_inside)
        {
            if ((z1 - z_lower) * (z2 - z_lower) < 0.0f)
                add_interp((z_lower - z1) / z_diff);
            if ((z1 - z_upper) * (z2 - z_upper) < 0.0f)
                add_interp((z_upper - z1) / z_diff);
        }
        else if (z1_inside ^ z2_inside)
        {
            if ((z1 - z_lower) * (z2 - z_lower) < 0.0f)
                add_interp((z_lower - z1) / z_diff);
            else if ((z1 - z_upper) * (z2 - z_upper) < 0.0f)
                add_interp((z_upper - z1) / z_diff);
        }
    }

    std::vector<Vec2> hull;
    hull.reserve(64);
    double weighted_centroid_x = 0.0, weighted_centroid_y = 0.0;
    for (uint32_t component_index : active)
    {
        auto &points = comp_points[component_index];
        if (points.size() < 3)
            continue;
        // Sort and deduplicate points
        auto point_compare = [](const Vec2 &a, const Vec2 &b)
        { return (a.x < b.x) || (a.x == b.x && a.y < b.y); };
        std::sort(points.begin(), points.end(), point_compare);
        points.erase(std::unique(points.begin(), points.end(), [](const Vec2 &a, const Vec2 &b)
                                 { return a.x == b.x && a.y == b.y; }),
                     points.end());
        if (points.size() < 3)
            continue;
        hull = monotonic_chain(points);
        size_t hull_size = hull.size();
        if (hull_size < 3)
            continue;
        for (const Vec2 &p : hull) {
            if (p.x < min_x) min_x = p.x;
            if (p.x > max_x) max_x = p.x;
            if (p.y < min_y) min_y = p.y;
            if (p.y > max_y) max_y = p.y;
        }
        has_points = true;
        double area = 0.0, centroid_x = 0.0, centroid_y = 0.0;
        for (size_t k = 0; k < hull_size; ++k)
        {
            const Vec2 &p0 = hull[k];
            const Vec2 &p1 = hull[(k + 1) % hull_size];
            double cross = (double)p0.x * p1.y - (double)p1.x * p0.y;
            area += cross;
            centroid_x += (p0.x + p1.x) * cross;
            centroid_y += (p0.y + p1.y) * cross;
        }
        area *= 0.5;
        if (area == 0.0)
            continue;
        double area_abs = std::fabs(area);
        double inv_6_area = 1.0 / (6.0 * area);
        weighted_centroid_x += (centroid_x * inv_6_area) * area_abs;
        weighted_centroid_y += (centroid_y * inv_6_area) * area_abs;
        out_area += (float)area_abs;
    }
    if (out_area > 0.f)
    {
        double inv = 1.0 / out_area;
        out_cog.x = (float)(weighted_centroid_x * inv);
        out_cog.y = (float)(weighted_centroid_y * inv);
    }
    if (has_points) {
        out_box.min_corner = {min_x, min_y};
        out_box.max_corner = {max_x, max_y};
        out_box.area = (max_x - min_x) * (max_y - min_y);
    } else {
        out_box.area = 0.f;
    }
}

// Driver function to calculate center of gravity using volume slicing and edge intersections
COGResult calc_cog_volume_edges_intersections(std::span<const Vec3> verts,
                                              std::span<const uVec2i> edges,
                                              BoundingBox3D full_box,
                                              float slice_height)
{
    uint32_t vertCount = verts.size();
    uint32_t edgeCount = edges.size();
    COGResult result;
    if (vertCount == 0 || edgeCount == 0 || slice_height <= 0.f)
        return result;

    float total_height = full_box.max_corner.z - full_box.min_corner.z;
    if (total_height <= 0.f)
        return result;

    // Precompute vertex data for cache efficiency
    std::vector<float> vert_z(vertCount);
    std::vector<Vec2> vert_xy(vertCount);
    for (uint32_t i = 0; i < vertCount; ++i)
    {
        vert_z[i] = verts[i].z;
        vert_xy[i] = {verts[i].x, verts[i].y};
    }

    uint32_t raw_slice_count = (uint32_t)std::ceil(total_height / slice_height);
    uint8_t slice_count = (uint8_t)std::min<uint32_t>(raw_slice_count, 255);
    float inv_slice_height = 1.0f / slice_height;

    // Precompute slice z-lowers & uppers
    std::vector<float> slice_z_lower(slice_count), slice_z_upper(slice_count);
    for (uint8_t slice_index = 0; slice_index < slice_count; ++slice_index)
    {
        float z_lower = full_box.min_corner.z + slice_index * slice_height;
        slice_z_lower[slice_index] = z_lower;
        slice_z_upper[slice_index] = std::min(full_box.max_corner.z, z_lower + slice_height);
    }

    // No per-slice struct allocation needed.

    std::vector<std::vector<uint32_t>> slice_edges;
    bucket_edges_per_slice(slice_edges, edges, vert_z,
                           full_box.min_corner.z, slice_height, inv_slice_height, slice_count);

    // Global union-find (iterative find to reduce recursion overhead)
    std::vector<uint32_t> uf_parent(vertCount);
    std::vector<uint8_t> uf_rank(vertCount, 0);
    for (uint32_t i = 0; i < vertCount; ++i)
        uf_parent[i] = i;
    auto uf_find = [&](uint32_t x)
    {
        while (uf_parent[x] != x)
        {
            uf_parent[x] = uf_parent[uf_parent[x]]; // path halving
            x = uf_parent[x];
        }
        return x;
    };
    auto uf_unite = [&](uint32_t a, uint32_t b)
    {
        a = uf_find(a);
        b = uf_find(b);
        if (a == b)
            return;
        if (uf_rank[a] < uf_rank[b])
            std::swap(a, b);
        uf_parent[b] = a;
        if (uf_rank[a] == uf_rank[b])
            ++uf_rank[a];
    };

    std::vector<std::vector<uint32_t>> slice_vertices(slice_count);
    for (uint32_t vertex_id = 0; vertex_id < vertCount; ++vertex_id)
    {
        float z = vert_z[vertex_id];
        if (z < full_box.min_corner.z || z > full_box.max_corner.z)
            continue;
        int slice_index = (int)((z - full_box.min_corner.z) * inv_slice_height);
        if (slice_index >= 0 && slice_index < slice_count)
            slice_vertices[slice_index].push_back(vertex_id);
    }

    // Union all edges globally for connectivity
    for (uint32_t edge_index = 0; edge_index < edgeCount; ++edge_index)
    {
        const uVec2i &edge = edges[edge_index];
        uf_unite(edge.x, edge.y);
    }

    // Precompute component roots for all vertices
    std::vector<uint32_t> vertex_comp(vertCount);
    for (uint32_t i = 0; i < vertCount; ++i)
    {
        vertex_comp[i] = uf_find(i);
    }
    // Linear component id compression (avoids unordered_set)
    std::vector<uint32_t> cid_to_index(vertCount, UINT32_MAX);
    uint32_t num_components = 0;
    for (uint32_t i = 0; i < vertCount; ++i)
    {
        uint32_t component_id = vertex_comp[i];
        if (cid_to_index[component_id] == UINT32_MAX)
        {
            cid_to_index[component_id] = num_components++;
        }
    }

    // Collect per-slice data
    result.slices.reserve(slice_count);
    Vec3 overall{0, 0, 0};
    float total_area = 0.f;
    for (uint8_t slice_index = 0; slice_index < slice_count; ++slice_index)
    {
        if (slice_edges[slice_index].empty())
        {
            // Even if empty, add a slice with zero area
            float mid_z = 0.5f * (slice_z_lower[slice_index] + slice_z_upper[slice_index]);
            BoundingBox2D empty_box;
            empty_box.area = 0.f;
            result.slices.push_back({0.f, empty_box, {0.f, 0.f}, mid_z});
            continue;
        }
        float z_lower = slice_z_lower[slice_index];
        float z_upper = slice_z_upper[slice_index];
        Vec2 slice_cog;
        float slice_area;
        BoundingBox2D slice_box;
        build_slice_islands(
            vert_xy, vert_z, edges, slice_edges[slice_index],
            z_lower, z_upper, slice_vertices[slice_index],
            vertex_comp, cid_to_index, num_components,
            slice_cog, slice_area, slice_box);
        float mid_z = 0.5f * (z_lower + z_upper);
        result.slices.push_back({slice_area, slice_box, slice_cog, mid_z});
        if (slice_area <= 0.f)
            continue;
        overall.x += slice_cog.x * slice_area;
        overall.y += slice_cog.y * slice_area;
        overall.z += mid_z * slice_area;
        total_area += slice_area;
    }
    if (total_area > 0.f)
    {
        overall.x /= total_area;
        overall.y /= total_area;
        overall.z /= total_area;
    }
    result.overall_cog = overall;
    return result;
}