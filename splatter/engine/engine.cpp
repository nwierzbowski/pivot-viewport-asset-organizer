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
        // if (e.x >= vertCount || e.y >= vertCount) {
        //     std::cerr << "Invalid edge index: e.x=" << e.x << ", e.y=" << e.y << ", vertCount=" << vertCount << std::endl;
        //     continue; // Skip invalid edges or handle as needed
        // }
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
        // if (e.x >= vertCount || e.y >= vertCount) {
        //     continue; // Skip invalid edges
        // }
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

    std::cerr << "Finished classification" << std::endl;
}

void prepare_object_batch(std::span<const Vec3> verts_flat, std::span<const uVec2i> edges_flat, std::span<const uint32_t> vert_counts, std::span<const uint32_t> edge_counts, std::span<Quaternion> out_rots, std::span<Vec3> out_trans)
{
    //Print
    std::cerr << "Entered prepare_object_batch" << std::endl;
    std::cerr << "verts_flat size: " << verts_flat.size() << ", edges_flat size: " << edges_flat.size() << std::endl;
    std::cerr << "vert_counts size: " << vert_counts.size() << ", edge_counts size: " << edge_counts.size() << std::endl;
    std::cerr << "num_objects: " << vert_counts.size() << std::endl;


    uint32_t num_objects = vert_counts.size();
    if (num_objects == 0 || edge_counts.size() != num_objects || out_rots.size() != num_objects || out_trans.size() != num_objects)
        return;

    uint32_t vert_offset = 0;
    uint32_t edge_offset = 0;
    for (uint32_t i = 0; i < num_objects; ++i)
    {
        uint32_t v_count = vert_counts[i];
        uint32_t e_count = edge_counts[i];

        //print counts
        std::cerr << "Object " << i << ": vertCount=" << v_count << ", edgeCount=" << e_count << std::endl;
        std::span<const Vec3> obj_verts = verts_flat.subspan(vert_offset, v_count);
        std::span<const uVec2i> obj_edges = edges_flat.subspan(edge_offset, e_count);
        std::span<Quaternion> obj_rot = out_rots.subspan(i, 1);
        std::span<Vec3> obj_trans = out_trans.subspan(i, 1);
        standardize_object_transform(obj_verts, obj_edges, obj_rot, obj_trans);
        vert_offset += v_count;
        edge_offset += e_count;
    }
}

void group_objects(std::span<Vec3> verts_flat, std::span<uVec2i> edges_flat, std::vector<uint32_t>& vert_counts, std::vector<uint32_t>& edge_counts, std::span<const Vec3> offsets, std::span<const Quaternion> rotations, std::span<const Vec3> scales, std::span<const uint32_t> object_counts)
{
    std::cerr << "Entered group_objects" << std::endl;
    

    uint32_t num_groups = object_counts.size();
    uint32_t num_objects = vert_counts.size();

    std::cerr << "verts_flat size: " << verts_flat.size() << ", edges_flat size: " << edges_flat.size() << std::endl;
    std::cerr << "vert_counts size: " << vert_counts.size() << ", edge_counts size: " << edge_counts.size() << std::endl;

    std::cerr << "num_groups: " << num_groups << ", offsets size: " << offsets.size() << ", rotations size: " << rotations.size() << ", scales size: " << scales.size() << std::endl;

    if (num_groups == 0 || num_objects == 0 || offsets.size() != num_objects || rotations.size() != num_objects || scales.size() != num_objects)
        return;

    // Transform vertices and edges in place
    uint32_t group_vert_offset = 0, group_edge_offset = 0, group_obj_index = 0;
    for (uint32_t group = 0; group < num_groups; ++group)
    {
        uint32_t num_objs_in_group = object_counts[group];
        uint32_t group_vert_count = 0;
        uint32_t group_edge_count = 0;
        
        for (uint32_t j = 0; j < num_objs_in_group; ++j)
        {
            group_vert_count += vert_counts[group_obj_index + j];
            group_edge_count += edge_counts[group_obj_index + j];
        }

        std::span<uVec2i> group_edges = edges_flat.subspan(group_edge_offset, group_edge_count);
        std::span<Vec3> group_verts = verts_flat.subspan(group_vert_offset, group_vert_count);

        // Apply transformation to the entire group
        for (uint32_t j = 0; j < group_vert_count; ++j)
        {
            Vec3 &v = group_verts[j];
            v.x *= scales[group].x;
            v.y *= scales[group].y;
            v.z *= scales[group].z;
            Vec3 rotated = rotate_vertex_3D_quat(v, rotations[group]);
            rotated += offsets[group];
            group_verts[j] = rotated;
        }

        // Adjust edge indices per object within the group
        uint32_t local_v_off = 0;  // Start at group's vertex offset
        uint32_t local_e_off = 0;  // Start at group's edge offset
        for (uint32_t j = 0; j < num_objs_in_group; ++j)
        {
            uint32_t obj_vc = vert_counts[group_obj_index + j];  // Original per-object vert count
            uint32_t obj_ec = edge_counts[group_obj_index + j];  // Original per-object edge count

            for (uint32_t k = 0; k < obj_ec; ++k)
            {
                uVec2i &e = group_edges[local_e_off + k];
                e.x += local_v_off;
                e.y += local_v_off;
            }

            local_v_off += obj_vc;  // Increment for next object in group
            local_e_off += obj_ec;  // Increment for next object in group
        }

        // Update counts to reflect the group
        vert_counts[group] = group_vert_count;
        edge_counts[group] = group_edge_count;

        group_vert_offset += group_vert_count;
        group_edge_offset += group_edge_count;
        group_obj_index += num_objs_in_group;
    }

    // Resize to reflect the number of groups
    std::cerr << "Resizing vert_counts and edge_counts to " << num_groups << std::endl;
    vert_counts.resize(num_groups);
    edge_counts.resize(num_groups);
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
