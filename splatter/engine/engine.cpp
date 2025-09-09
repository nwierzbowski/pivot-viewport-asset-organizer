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

std::vector<std::vector<uint32_t>> build_adj_vertices(const uVec2i *edges, uint32_t edgeCount, uint32_t vertCount)
{
    std::vector<std::vector<uint32_t>> adj_verts(vertCount);
    if (!edges || edgeCount == 0)
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

        // Check if box.area is within epsilon of best_box.area
        // if (std::abs(box.area - best_box.area) < 1e-3)
        // {
        //     std::cout << "Found equivalent area at angle: " << -angle << std::endl;
        // }

        if (box.area < best_box.area)
        {
            // // Choose the box with the larger perimeter if areas are equivalent
            // if (std::abs(box.area - best_box.area) < 1e-3)
            // {
            //     if ((box.max_corner - box.min_corner).length_squared() >
            //         (best_box.max_corner - best_box.min_corner).length_squared())
            //     {
            //         best_box = box;
            //     }
            // }
            // else
            // {
            best_box = box;
            // }
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

void standardize_object_transform(const Vec3 *verts, uint32_t vertCount, const uVec2i *edges, uint32_t edgeCount, Quaternion *out_rot, Vec3 *out_trans)
{
    if (!verts || vertCount == 0 || vertCount == 0 || !edges || edgeCount == 0 || !out_rot || !out_trans)
        return;

    if (vertCount == 1)
    {
        *out_rot = {};
        *out_trans = {verts[0].x, verts[0].y, verts[0].z};
        return;
    }

    auto adj_verts = build_adj_vertices(edges, edgeCount, vertCount);
    auto voxel_map = build_voxel_map(verts, vertCount, 0.03f);

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

    COGResult cog_result = calc_cog_volume_edges_intersections(verts, vertCount, edges, edgeCount, full_3DBB, 0.02f);

    // auto end = std::chrono::high_resolution_clock::now();
    // auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);
    // std::cout << "COG Full Calc Time: " << (float)duration.count() / 1000000 << " ms" << std::endl;
    COGResult working_cog_result = {cog_result.overall_cog, cog_result.slices};

    rotate_vector(working_cog_result.overall_cog, angle_to_forward);
    for (auto &slice : working_cog_result.slices)
    {
        rotate_vector(slice.centroid, angle_to_forward);
    }

    uint8_t curr_front_axis = 0;

    if (is_ground(working_verts, working_cog_result, full_3DBB))
    {
        std::cout << "Classified as Ground" << std::endl;

        if (snapStandToYN(working_cog_result, full_2DBB, curr_front_axis))
        {
            std::cout << "Snapped to Stand Axis" << std::endl;
        }
        else if (snapHighToYN(working_cog_result, full_2DBB, curr_front_axis))
        {
            std::cout << "Snapped to High Axis" << std::endl;
        }
        else
        {

            
            if (isSmall(full_3DBB))
            {
                snapDenseToYN(working_cog_result, full_2DBB, curr_front_axis);
                std::cout << "Small, snapped dense to +Y" << std::endl;
                curr_front_axis -= 2;
            }
            else
            {
                if (isSquarish(full_3DBB))
                {
                    snapDenseToYN(working_cog_result, full_2DBB, curr_front_axis);
                    std::cout << "Large, snapped dense to -Y" << std::endl;
                }
                else
                {
                    alignLongAxisToX(full_3DBB, curr_front_axis);
                    std::cout << "Aligned long axis to +X" << std::endl;
                    snapDenseToYN(working_cog_result, full_2DBB, curr_front_axis, {0, 2});
                }
            }
        }
    }
    else if (is_wall(working_verts, full_3DBB, curr_front_axis))
    {
        std::cout << "Classified as Wall" << std::endl;
    }
    else
    {
        std::cout << "Classified as Ceiling" << std::endl;
    }

    angle_to_forward += static_cast<float>(curr_front_axis) * M_PI_2;

    *out_rot = Quaternion({0, 0, 1}, angle_to_forward); // Rotation to align object front with +Y axis

    Vec3 final_cog = cog_result.overall_cog;
    rotate_vector(final_cog, angle_to_forward);
    *out_trans = final_cog;
}

void prepare_object_batch(const Vec3 *verts_flat, const uVec2i *edges_flat, const uint32_t *vert_counts, const uint32_t *edge_counts, uint32_t num_objects, Quaternion *out_rots, Vec3 *out_trans)
{
    if (!verts_flat || !edges_flat || !vert_counts || !edge_counts || num_objects == 0 || !out_rots || !out_trans)
        return;

    uint32_t vert_offset = 0;
    uint32_t edge_offset = 0;
    for (uint32_t i = 0; i < num_objects; ++i)
    {
        uint32_t v_count = vert_counts[i];
        uint32_t e_count = edge_counts[i];
        standardize_object_transform(&verts_flat[vert_offset], v_count, &edges_flat[edge_offset], e_count, &out_rots[i], &out_trans[i]);
        vert_offset += v_count;
        edge_offset += e_count;
    }
}

void group_objects(Vec3 *verts_flat, uVec2i *edges_flat, const uint32_t *vert_counts, const uint32_t *edge_counts, const Vec3 *offsets, const Quaternion *rotations, const Vec3 *scales, uint32_t num_objects)
{
    if (!verts_flat || !edges_flat || !vert_counts || !edge_counts || !offsets || !rotations || !scales || num_objects == 0)
        return;

    // Calculate total sizes
    uint32_t total_verts = 0, total_edges = 0;
    for (uint32_t i = 0; i < num_objects; ++i)
    {
        total_verts += vert_counts[i];
        total_edges += edge_counts[i];
    }

    // Transform vertices and edges in place
    uint32_t vert_offset = 0, edge_offset = 0;
    for (uint32_t i = 0; i < num_objects; ++i)
    {
        uint32_t v_count = vert_counts[i];
        uint32_t e_count = edge_counts[i];

        // Print scale, offset, rotation
        std::cout << "Object " << i << " Scale: (" << scales[i].x << ", " << scales[i].y << ", " << scales[i].z << ")" << std::endl;
        std::cout << "Object " << i << " Offset: (" << offsets[i].x << ", " << offsets[i].y << ", " << offsets[i].z << ")" << std::endl;
        std::cout << "Object " << i << " Rotation: (" << rotations[i].w << ", " << rotations[i].x << ", " << rotations[i].y << ", " << rotations[i].z << ")" << std::endl;

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

void apply_rotation(Vec3 *verts, uint32_t vertCount, const Quaternion &rotation)
{
    if (!verts || vertCount == 0)
        return;

    for (uint32_t i = 0; i < vertCount; ++i)
    {
        verts[i] = rotate_vertex_3D_quat(verts[i], rotation);
    }
}
