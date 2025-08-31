#include "analysis.h"
#include "vec.h"
#include "geo2d.h"

#include <vector>
#include <cstdint>
#include <unordered_set>

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

    std::vector<uint8_t> in_slice(vertCount, 0);
    for (uint32_t vi : s.vert_indices) in_slice[vi] = 1;

    std::vector<int32_t> vertex_to_island(vertCount, -1);
    std::vector<std::vector<uint32_t>> islands;
    std::vector<std::unordered_set<uint32_t>> island_frontiers;

    islands.reserve(s.vert_indices.size() / 4 + 1);
    island_frontiers.reserve(islands.capacity());

    for (uint32_t vi : s.vert_indices)
    {
        if (vertex_to_island[vi] != -1) continue;

        const auto &nbrs = adj_verts[vi];

        std::vector<int32_t> neighbor_islands;
        neighbor_islands.reserve(4);
        {
            std::unordered_set<int32_t> dedup;
            for (uint32_t n : nbrs)
            {
                if (!in_slice[n]) continue;
                int32_t iid = vertex_to_island[n];
                if (iid != -1 && dedup.insert(iid).second)
                    neighbor_islands.push_back(iid);
            }
        }

        if (neighbor_islands.empty())
        {
            int32_t new_id = (int32_t)islands.size();
            islands.emplace_back().push_back(vi);
            vertex_to_island[vi] = new_id;
            island_frontiers.emplace_back();
            for (uint32_t n : nbrs)
                if (in_slice[n] && vertex_to_island[n] == -1)
                    island_frontiers[new_id].insert(n);
        }
        else if (neighbor_islands.size() == 1)
        {
            int32_t iid = neighbor_islands[0];
            islands[iid].push_back(vi);
            vertex_to_island[vi] = iid;
            island_frontiers[iid].erase(vi);
            for (uint32_t n : nbrs)
                if (in_slice[n] && vertex_to_island[n] == -1)
                    island_frontiers[iid].insert(n);
        }
        else
        {
            int32_t base = neighbor_islands[0];
            islands[base].push_back(vi);
            vertex_to_island[vi] = base;

            for (size_t k = 1; k < neighbor_islands.size(); ++k)
            {
                int32_t other = neighbor_islands[k];
                if (other == base) continue;

                for (uint32_t vj : islands[other])
                {
                    islands[base].push_back(vj);
                    vertex_to_island[vj] = base;
                }
                islands[other].clear();

                for (uint32_t f : island_frontiers[other])
                    if (vertex_to_island[f] == -1)
                        island_frontiers[base].insert(f);
                island_frontiers[other].clear();
            }

            for (uint32_t n : nbrs)
                if (in_slice[n] && vertex_to_island[n] == -1)
                    island_frontiers[base].insert(n);

            for (uint32_t vj : islands[base])
                island_frontiers[base].erase(vj);
        }
    }

    for (const auto &island : islands)
    {
        if (island.empty()) continue;
        std::vector<Vec3> islandVerts;
        islandVerts.reserve(island.size());
        for (uint32_t vi : island)
            islandVerts.push_back(verts[vi]);

        auto hull = convex_hull_2D(islandVerts, &Vec3::z, s.z_lower, s.z_upper);
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
    const uint8_t slice_count = 10;
    const float slice_height = (full_box.max_corner.z - full_box.min_corner.z) / (slice_count);

    std::vector<Slice> slices(slice_count);

    // Init slices
    for (uint8_t i = 0; i < slice_count; ++i)
    {
        slices[i].z_upper = full_box.min_corner.z + (i + 1) * slice_height;
        slices[i].z_lower = full_box.min_corner.z + i * slice_height;
        slices[i].vert_indices.reserve(vertCount / slice_count);
    }

    // Distribute vertices into slices
    for (uint32_t i = 0; i < vertCount; i++)
    {
        const Vec3 &v = verts[i];
        const uint8_t slice_index = static_cast<uint8_t>((v.z - full_box.min_corner.z) / slice_height);
        slices[slice_index].vert_indices.push_back(i);
    }

    // Calculate convex hulls for the connected islands in each slice
    for (Slice &s : slices)
    {
        build_slice_island_hulls(s, verts, vertCount, adj_verts);

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
    }

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

    return overall_cog;
}