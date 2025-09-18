#include "engine.h"
#include "share/vec.h"
#include "object/computation/voxel.h"
#include "object/computation/chull.h"
#include "object/computation/wire_detect.h"
#include "object/util/geo2d.h"
#include "object/analysis/ground.h"
#include "object/analysis/wall.h"
#include "object/computation/cog.h"

#include <vector>
#include <chrono>
#include <iostream>
#include <algorithm>
#include <cstdint>
#include <span>

std::vector<std::vector<uint32_t>> build_adj_vertices(std::span<const uVec2i> edges, uint32_t vertCount)
{
    std::vector<std::vector<uint32_t>> adj_verts(vertCount);
    uint32_t edgeCount = edges.size();
    if (edgeCount == 0)
        return adj_verts;

    // --- Reserve memory for each adjacency list ---
    std::vector<uint32_t> degrees(vertCount, 0);
    for (uint32_t i = 0; i < edgeCount; ++i)
    {
        const uVec2i &e = edges[i];
        degrees[e.x]++;
        degrees[e.y]++;
    }

    for (uint32_t i = 0; i < vertCount; ++i)
    {
        adj_verts[i].reserve(degrees[i]);
    }

    // Build adjacency list
    for (uint32_t i = 0; i < edgeCount; ++i)
    {
        const uVec2i &e = edges[i];
        adj_verts[e.x].push_back(e.y);
        adj_verts[e.y].push_back(e.x);
    }

    // Remove duplicates and sort each adjacency list
    for (auto &neighbors : adj_verts)
    {
        std::sort(neighbors.begin(), neighbors.end());
        neighbors.erase(std::unique(neighbors.begin(), neighbors.end()), neighbors.end());
    }

    return adj_verts;
}

std::vector<bool> calc_mask(uint32_t vertCount, const std::vector<std::vector<uint32_t>> &adj_verts, VoxelMap &voxel_map)
{
    std::vector<bool> mask(vertCount, false);

    auto voxel_guesses = guess_wire_voxels(voxel_map);
    select_wire_verts(vertCount, adj_verts, voxel_guesses, voxel_map, mask);
    return mask;
}

float calc_forward_angle(std::vector<Vec2> &hull)
{
    std::vector<float> angles = get_edge_angles_2D(hull);
    BoundingBox2D best_box;
    best_box.area = std::numeric_limits<float>::infinity();

    std::vector<Vec2> rot_hull(hull.size());

    for (float angle : angles)
    {
        rotate_points_2D(hull, -angle, rot_hull);
        BoundingBox2D box = compute_aabb_2D(rot_hull);
        box.rotation_angle = -angle;

        if (box.area < best_box.area)
        {
            best_box = box;
        }
    }

    return best_box.rotation_angle;
}

template <HasXY V>
void rotate_vector(V &v, float angle)
{
    float cos_angle = std::cos(angle);
    float sin_angle = std::sin(angle);
    float x_new = v.x * cos_angle - v.y * sin_angle;
    float y_new = v.x * sin_angle + v.y * cos_angle;
    v.x = x_new;
    v.y = y_new;
}

void standardize_object_transform(std::span<const Vec3> verts, std::span<const uVec2i> edges, std::span<Quaternion> out_rot, std::span<Vec3> out_trans)
{
    uint32_t vertCount = verts.size();
    uint32_t edgeCount = edges.size();
    if (vertCount == 0 || edgeCount == 0 || out_rot.empty() || out_trans.empty())
        return;

    if (vertCount == 1)
    {
        out_rot[0] = {};
        out_trans[0] = {verts[0].x, verts[0].y, verts[0].z};
        return;
    }

    auto adj_verts = build_adj_vertices(edges, vertCount);
    auto voxel_map = build_voxel_map(verts, 0.03f);

    auto mask = calc_mask(vertCount, adj_verts, voxel_map);

    // Create a copy of the original vertices masking for wires
    std::vector<Vec3> working_verts;
    working_verts.reserve(vertCount);

    for (uint32_t i = 0; i < vertCount; ++i)
        if (!mask[i])
            working_verts.push_back(verts[i]);

    // Global sort for good convex hull cache locality
    std::sort(working_verts.begin(), working_verts.end());

    // Get full 2d convex hull and calculate the angle the object is facing
    std::vector<Vec2> full_hull2D = monotonic_chain(working_verts);
    float angle_to_forward = calc_forward_angle(full_hull2D);

    // Rotate working vertices to align object with +Y axis
    rotate_points_2D(working_verts, angle_to_forward, working_verts);
    rotate_points_2D(full_hull2D, angle_to_forward, full_hull2D);

    // Re-sort after rotation to maintain order for subsequent convex hull computations
    std::sort(working_verts.begin(), working_verts.end());

    auto full_3DBB = compute_aabb_3D(working_verts);
    auto full_2DBB = compute_aabb_2D(working_verts);

    // auto start = std::chrono::high_resolution_clock::now();

    COGResult cog_result = calc_cog_volume_edges_intersections(verts, edges, full_3DBB, 0.01f);

    // auto end = std::chrono::high_resolution_clock::now();
    // auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);
    // std::cerr << "COG Full Calc Time: " << (float)duration.count() / 1000000 << " ms" << std::endl;
    COGResult working_cog_result = {cog_result.overall_cog, cog_result.slices};

    rotate_vector(working_cog_result.overall_cog, angle_to_forward);
    for (auto &slice : working_cog_result.slices)
    {
        rotate_vector(slice.centroid, angle_to_forward);
    }

    uint8_t curr_front_axis = 0;
    if (is_flat(working_verts, working_cog_result, full_3DBB, curr_front_axis))
    {
        std::cerr << "Classified as Flat" << std::endl;
    }
    else if (is_ground(working_verts, working_cog_result, full_3DBB))
    {
        std::cerr << "Classified as Ground" << std::endl;

        if (snapStandToYN(working_cog_result, full_2DBB, curr_front_axis))
        {
            std::cerr << "Snapped to Stand Axis" << std::endl;
        }
        else if (snapHighToYN(working_cog_result, full_2DBB, curr_front_axis))
        {
            std::cerr << "Snapped to High Axis" << std::endl;
        }
        else
        {

            if (isSmall(full_3DBB))
            {
                snapDenseToYN(working_cog_result, full_2DBB, curr_front_axis);
                std::cerr << "Small, snapped dense to +Y" << std::endl;
                curr_front_axis -= 2;
            }
            else
            {
                if (isSquarish(full_3DBB))
                {
                    snapDenseToYN(working_cog_result, full_2DBB, curr_front_axis);
                    std::cerr << "Large, snapped dense to -Y" << std::endl;
                }
                else
                {
                    alignLongAxisToX(full_3DBB, curr_front_axis);
                    std::cerr << "Aligned long axis to +X" << std::endl;
                    snapDenseToYN(working_cog_result, full_2DBB, curr_front_axis, {0, 2});
                }
            }
        }
    }
    else if (is_wall(working_verts, full_3DBB, curr_front_axis))
    {
        std::cerr << "Classified as Wall" << std::endl;
    }
    else
    {
        std::cerr << "Classified as Ceiling" << std::endl;
    }

    angle_to_forward += static_cast<float>(curr_front_axis) * M_PI_2;

    out_rot[0] = Quaternion({0, 0, 1}, angle_to_forward); // Rotation to align object front with +Y axis

    Vec3 final_cog = cog_result.overall_cog;
    rotate_vector(final_cog, angle_to_forward);
    out_trans[0] = final_cog;
}

void prepare_object_batch(std::span<const Vec3> verts_flat, std::span<const uVec2i> edges_flat, std::span<const uint32_t> vert_counts, std::span<const uint32_t> edge_counts, std::span<Quaternion> out_rots, std::span<Vec3> out_trans)
{
    uint32_t num_objects = vert_counts.size();
    if (num_objects == 0 || edge_counts.size() != num_objects || out_rots.size() != num_objects || out_trans.size() != num_objects)
        return;

    uint32_t vert_offset = 0;
    uint32_t edge_offset = 0;
    for (uint32_t i = 0; i < num_objects; ++i)
    {
        uint32_t v_count = vert_counts[i];
        uint32_t e_count = edge_counts[i];
        std::span<const Vec3> obj_verts = verts_flat.subspan(vert_offset, v_count);
        std::span<const uVec2i> obj_edges = edges_flat.subspan(edge_offset, e_count);
        std::span<Quaternion> obj_rot = out_rots.subspan(i, 1);
        std::span<Vec3> obj_trans = out_trans.subspan(i, 1);
        standardize_object_transform(obj_verts, obj_edges, obj_rot, obj_trans);
        vert_offset += v_count;
        edge_offset += e_count;
    }
}

void group_objects(std::span<Vec3> verts_flat, std::span<uVec2i> edges_flat, std::span<const uint32_t> vert_counts, std::span<const uint32_t> edge_counts, std::span<const Vec3> offsets, std::span<const Quaternion> rotations, std::span<const Vec3> scales)
{
    uint32_t num_objects = vert_counts.size();
    if (num_objects == 0 || edge_counts.size() != num_objects || offsets.size() != num_objects || rotations.size() != num_objects || scales.size() != num_objects)
        return;

    // Transform vertices and edges in place
    uint32_t vert_offset = 0, edge_offset = 0;
    for (uint32_t i = 0; i < num_objects; ++i)
    {
        uint32_t v_count = vert_counts[i];
        uint32_t e_count = edge_counts[i];

        // Rotate and offset vertices
        for (uint32_t j = 0; j < v_count; ++j)
        {
            Vec3 &v = verts_flat[vert_offset + j];
            v.x *= scales[i].x;
            v.y *= scales[i].y;
            v.z *= scales[i].z;
            Vec3 rotated = rotate_vertex_3D_quat(v, rotations[i]);
            rotated += offsets[i];
            verts_flat[vert_offset + j] = rotated;
        }

        // Adjust edge indices
        for (uint32_t j = 0; j < e_count; ++j)
        {
            edges_flat[edge_offset + j].x += vert_offset;
            edges_flat[edge_offset + j].y += vert_offset;
        }

        vert_offset += v_count;
        edge_offset += e_count;
    }
}

void apply_rotation(Vec3* verts, uint32_t vertCount, const Quaternion &rotation)
{
    std::span<Vec3> verts_span(verts, vertCount);
    if (verts_span.empty())
        return;

    for (auto &v : verts_span)
    {
        v = rotate_vertex_3D_quat(v, rotation);
    }
}
