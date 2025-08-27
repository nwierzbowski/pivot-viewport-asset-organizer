#include "bounds.h"
#include "util.h"
#include "chull.h"
#include "geo2d.h"
#include "wire_detect.h"

#include <Eigen/Eigenvalues>

#include <iostream>
#include <cstdint>
#include <vector>
#include <chrono>


void build_adj_vertices(const uVec2i *edges, uint32_t edgeCount, std::vector<std::vector<uint32_t>> &out_adj_verts)
{
    if (!edges || edgeCount == 0)
        return;

    // --- Reserve memory for each adjacency list ---
    std::vector<uint32_t> degrees(out_adj_verts.size(), 0);
    for (uint32_t i = 0; i < edgeCount; ++i)
    {
        const uVec2i &e = edges[i];
        degrees[e.x]++;
        degrees[e.y]++;
    }

    
    for (uint32_t i = 0; i < out_adj_verts.size(); ++i)
    {
        out_adj_verts[i].reserve(degrees[i]);
    }

    // Build adjacency list
    for (uint32_t i = 0; i < edgeCount; ++i)
    {
        const uVec2i &e = edges[i];
        out_adj_verts[e.x].push_back(e.y);
        out_adj_verts[e.y].push_back(e.x);
    }

    // Remove duplicates and sort each adjacency list
    for (auto &neighbors : out_adj_verts)
    {
        std::sort(neighbors.begin(), neighbors.end());
        neighbors.erase(std::unique(neighbors.begin(), neighbors.end()), neighbors.end());
    }
}



void align_min_bounds(const Vec3 *verts, const Vec3 *vert_norms, uint32_t vertCount, const uVec2i *edges, uint32_t edgeCount, Vec3 *out_rot, Vec3 *out_trans)
{
    if (!verts || vertCount == 0 || !vert_norms || vertCount == 0 || !edges || edgeCount == 0 || !out_rot || !out_trans)
        return;

    if (vertCount == 1)
    {
        *out_rot = {0, 0, 0};
        *out_trans = {verts[0].x, verts[0].y, verts[0].z};
        return;
    }

    // Calculate vertex adjacency lists
    std::vector<std::vector<uint32_t>> adj_verts(vertCount);
    auto start = std::chrono::high_resolution_clock::now();
    build_adj_vertices(edges, edgeCount, adj_verts);

    auto voxel_map = build_voxel_map(verts, vertCount, 0.03f);

    std::vector<VoxelKey> voxel_guesses;
    calculate_voxel_map_stats(voxel_map, vert_norms, verts, voxel_guesses);

    auto is_wire = select_wire_verts(verts, vert_norms, vertCount, adj_verts, voxel_guesses, voxel_map);

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    std::cout << "Time: " << duration.count() << " ms" << std::endl;

    std::vector<Vec2> hull = convex_hull_2D(verts, vertCount, is_wire);
    std::vector<float> angles = get_edge_angles_2D(hull);
    BoundingBox2D best_box;
    best_box.area = std::numeric_limits<float>::infinity();

    std::vector<Vec2> rot_hull(hull.size());
    for (float angle : angles)
    {
        rotate_points_2D(hull, -angle, rot_hull);
        BoundingBox2D box = compute_aabb_2D(rot_hull, -angle);
        if (box.area < best_box.area)
            best_box = box;
    }

    *out_rot = {0, 0, best_box.rotation_angle};
    *out_trans = {0, 0, 0};
    return;
}