#include "analysis.h"
#include "vec.h"
#include "geo2d.h"

#include <vector>
#include <cstdint>
#include <iostream>

std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3> &verts, BoundingBox3D full_box)
{
    return monotonic_chain(verts, &Vec3::z, full_box.min_corner.z, full_box.min_corner.z + 0.001);
}

float calc_ratio_full_to_base(const BoundingBox2D &full_box, const BoundingBox2D &base_box)
{
    if (base_box.area == 0)
        return 0;
    return full_box.area / base_box.area;
}

// Build per-slice edge buckets: slice_edges[si] contains indices of edges overlapping slice si.
static inline void bucket_edges_per_slice(
    std::vector<std::vector<uint32_t>> &slice_edges,
    const uVec2i *edges,
    uint32_t edgeCount,
    const std::vector<float> &vert_z,
    float z0,
    float slice_height,
    float inv_slice_height,
    uint8_t slice_count)
{
    slice_edges.assign(slice_count, {});
    for (uint32_t ei = 0; ei < edgeCount; ++ei)
    {
        const uVec2i &e = edges[ei];
        float zA = vert_z[e.x];
        float zB = vert_z[e.y];
        float zmin = zA < zB ? zA : zB;
        float zmax = zA > zB ? zA : zB;
        float span_top = z0 + slice_height * slice_count;
        if (zmax <= z0 || zmin >= span_top)
            continue;
        int first = (int)std::ceil((zmin - z0) * inv_slice_height);
        int last = (int)std::floor((zmax - z0) * inv_slice_height);
        if (first > last)
            continue;
        if (last < 0 || first >= slice_count)
            continue;
        if (first < 0)
            first = 0;
        if (last >= slice_count)
            last = slice_count - 1;
        for (int si = first; si <= last; ++si)
            slice_edges[si].push_back(ei);
    }
}

// Build slice islands and directly compute aggregated area and COG (avoids storing hulls)
static inline void build_slice_islands(
    const std::vector<Vec2> &vert_xy,
    const std::vector<float> &vert_z,
    const uVec2i *edges,
    const std::vector<uint32_t> &slice_edge_indices,
    float z_lower,
    float z_upper,
    const std::vector<uint32_t> &slice_verts,
    const std::vector<uint32_t> &vertex_comp,
    const std::vector<uint32_t> &cid_to_index,
    uint32_t num_components,
    Vec2 &out_cog,
    float &out_area)
{
    out_cog = {0.f, 0.f};
    out_area = 0.f;
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

    auto ensure_active = [&](uint32_t idx)
    {
        if (comp_gen[idx] != global_gen)
        {
            comp_points[idx].clear();
            comp_gen[idx] = global_gen;
            active.push_back(idx);
        }
    };

    // Add vertex points
    for (uint32_t vid : slice_verts)
    {
        uint32_t idx = cid_to_index[vertex_comp[vid]];
        ensure_active(idx);
        comp_points[idx].push_back(vert_xy[vid]);
    }
    // Edge intersection points
    for (uint32_t ei : slice_edge_indices)
    {
        const uVec2i &e = edges[ei];
        float zA = vert_z[e.x];
        float zB = vert_z[e.y];
        float d = zB - zA;
        if (std::abs(d) < 1e-8f)
            continue;
        uint32_t idx = cid_to_index[vertex_comp[e.x]];
        bool A_inside = (zA >= z_lower - EPS && zA <= z_upper + EPS);
        bool B_inside = (zB >= z_lower - EPS && zB <= z_upper + EPS);
        auto add_interp = [&](float t)
        { ensure_active(idx); const Vec2 &A_xy = vert_xy[e.x]; const Vec2 &B_xy = vert_xy[e.y]; comp_points[idx].push_back({A_xy.x + (B_xy.x - A_xy.x)*t, A_xy.y + (B_xy.y - A_xy.y)*t}); };
        if (!A_inside && !B_inside)
        {
            if ((zA - z_lower) * (zB - z_lower) < 0.0f)
                add_interp((z_lower - zA) / d);
            if ((zA - z_upper) * (zB - z_upper) < 0.0f)
                add_interp((z_upper - zA) / d);
        }
        else if (A_inside ^ B_inside)
        {
            if ((zA - z_lower) * (zB - z_lower) < 0.0f)
                add_interp((z_lower - zA) / d);
            else if ((zA - z_upper) * (zB - z_upper) < 0.0f)
                add_interp((z_upper - zA) / d);
        }
    }

    std::vector<Vec2> hull;
    hull.reserve(64);
    double weighted_cx = 0.0, weighted_cy = 0.0;
    for (uint32_t idx : active)
    {
        auto &pts = comp_points[idx];
        if (pts.size() < 3)
            continue;
        // Sort and dedup pts
        auto cmp = [](const Vec2 &a, const Vec2 &b)
        { return (a.x < b.x) || (a.x == b.x && a.y < b.y); };
        std::sort(pts.begin(), pts.end(), cmp);
        pts.erase(std::unique(pts.begin(), pts.end(), [](const Vec2 &a, const Vec2 &b)
                              { return a.x == b.x && a.y == b.y; }),
                  pts.end());
        if (pts.size() < 3)
            continue;
        hull = monotonic_chain(pts);
        size_t hsz = hull.size();
        if (hsz < 3)
            continue;
        double A = 0.0, Cx = 0.0, Cy = 0.0;
        for (size_t k = 0; k < hsz; ++k)
        {
            const Vec2 &p0 = hull[k];
            const Vec2 &p1 = hull[(k + 1) % hsz];
            double cross = (double)p0.x * p1.y - (double)p1.x * p0.y;
            A += cross;
            Cx += (p0.x + p1.x) * cross;
            Cy += (p0.y + p1.y) * cross;
        }
        A *= 0.5;
        if (A == 0.0)
            continue;
        double area_abs = std::fabs(A);
        double inv6A = 1.0 / (6.0 * A);
        weighted_cx += (Cx * inv6A) * area_abs;
        weighted_cy += (Cy * inv6A) * area_abs;
        out_area += (float)area_abs;
    }
    if (out_area > 0.f)
    {
        double inv = 1.0 / out_area;
        out_cog.x = (float)(weighted_cx * inv);
        out_cog.y = (float)(weighted_cy * inv);
    }
}

// Driver function
COGResult calc_cog_volume_edges_intersections(const Vec3 *verts,
                                              uint32_t vertCount,
                                              const uVec2i *edges,
                                              uint32_t edgeCount,
                                              BoundingBox3D full_box,
                                              float slice_height)
{
    COGResult result;
    if (!verts || !edges || vertCount == 0 || edgeCount == 0 || slice_height <= 0.f)
        return result;

    float total_h = full_box.max_corner.z - full_box.min_corner.z;
    if (total_h <= 0.f)
        return result;

    // Precompute vertex data for cache efficiency
    std::vector<float> vert_z(vertCount);
    std::vector<Vec2> vert_xy(vertCount);
    for (uint32_t i = 0; i < vertCount; ++i)
    {
        vert_z[i] = verts[i].z;
        vert_xy[i] = {verts[i].x, verts[i].y};
    }

    uint32_t raw_count = (uint32_t)std::ceil(total_h / slice_height);
    uint8_t slice_count = (uint8_t)std::min<uint32_t>(raw_count, 255);
    float inv_slice_height = 1.0f / slice_height;

    // Precompute slice z-lowers & uppers
    std::vector<float> slice_z_lower(slice_count), slice_z_upper(slice_count);
    for (uint8_t si = 0; si < slice_count; ++si)
    {
        float zl = full_box.min_corner.z + si * slice_height;
        slice_z_lower[si] = zl;
        slice_z_upper[si] = std::min(full_box.max_corner.z, zl + slice_height);
    }

    // No per-slice struct allocation needed.

    std::vector<std::vector<uint32_t>> slice_edges;
    bucket_edges_per_slice(slice_edges, edges, edgeCount, vert_z,
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
    for (uint32_t vid = 0; vid < vertCount; ++vid)
    {
        float z = vert_z[vid];
        if (z < full_box.min_corner.z || z > full_box.max_corner.z)
            continue;
        int si = (int)((z - full_box.min_corner.z) * inv_slice_height);
        if (si >= 0 && si < slice_count)
            slice_vertices[si].push_back(vid);
    }

    // Union all edges globally for connectivity
    for (uint32_t ei = 0; ei < edgeCount; ++ei)
    {
        const uVec2i &e = edges[ei];
        uf_unite(e.x, e.y);
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
        uint32_t cid = vertex_comp[i];
        if (cid_to_index[cid] == UINT32_MAX)
        {
            cid_to_index[cid] = num_components++;
        }
    }

    // Collect per-slice data
    result.slices.reserve(slice_count);
    Vec3 overall{0, 0, 0};
    float total_area = 0.f;
    for (uint8_t si = 0; si < slice_count; ++si)
    {
        if (slice_edges[si].empty())
        {
            // Even if empty, add a slice with zero area
            float mid_z = 0.5f * (slice_z_lower[si] + slice_z_upper[si]);
            result.slices.push_back({0.f, {0.f, 0.f}, mid_z});
            continue;
        }
        float z_lower = slice_z_lower[si];
        float z_upper = slice_z_upper[si];
        Vec2 slice_cog;
        float slice_area;
        build_slice_islands(
            vert_xy, vert_z, edges, slice_edges[si],
            z_lower, z_upper, slice_vertices[si],
            vertex_comp, cid_to_index, num_components,
            slice_cog, slice_area);
        float mid_z = 0.5f * (z_lower + z_upper);
        result.slices.push_back({slice_area, slice_cog, mid_z});
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
