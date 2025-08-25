#include "bounds.h"
#include "util.h"
#include "chull.h"

#include <Eigen/Eigenvalues>
#include <nanoflann.hpp>

#include <iostream>
#include <cstdint>
#include <vector>
#include <cmath>
#include <algorithm>
#include <stack>
#include <chrono>
#include <random>
#include <limits>

// Rotate points by angle (radians) around origin
void rotate_points_2D(const std::vector<Vec2> &points, float angle, std::vector<Vec2> &out)
{
    float cos_a = std::cos(angle);
    float sin_a = std::sin(angle);

    for (size_t i = 0; i < points.size(); ++i)
    {
        const Vec2 &p = points[i];
        out[i] = {
            p.x * cos_a - p.y * sin_a,
            p.x * sin_a + p.y * cos_a};
    }
}

// Compute axis-aligned bounding box of points
BoundingBox2D compute_aabb_2D(const std::vector<Vec2> &points, float rotation_angle)
{
    if (points.empty())
        return {};

    float min_x = points[0].x, max_x = points[0].x;
    float min_y = points[0].y, max_y = points[0].y;

    for (const Vec2 &p : points)
    {
        min_x = std::min(min_x, p.x);
        max_x = std::max(max_x, p.x);
        min_y = std::min(min_y, p.y);
        max_y = std::max(max_y, p.y);
    }

    BoundingBox2D box;
    box.min_corner = {min_x, min_y};
    box.max_corner = {max_x, max_y};
    box.area = (max_x - min_x) * (max_y - min_y);
    box.rotation_angle = rotation_angle;

    return box;
}

// Get unique edge directions from convex hull
std::vector<float> get_edge_angles_2D(const std::vector<Vec2> &hull)
{
    std::vector<float> angles;
    angles.reserve(hull.size());

    for (size_t i = 0; i < hull.size(); ++i)
    {
        size_t next = (i + 1) % hull.size();
        Vec2 edge = hull[next] - hull[i];

        if (edge.length_squared() > 1e-8f)
        { // Avoid degenerate edges
            float angle = std::atan2(edge.y, edge.x);

            // Normalize to [0, π) since we only need half rotations for rectangles
            // if (angle < 0) angle += M_PI;
            // if (angle >= M_PI) angle -= M_PI;

            angles.push_back(angle);
        }
    }

    // Remove duplicate angles (within tolerance)
    // std::sort(angles.begin(), angles.end());
    // auto last = std::unique(angles.begin(), angles.end(),
    //     [](float a, float b) { return std::abs(a - b) < 1e-6f; });
    // angles.erase(last, angles.end());

    return angles;
}

void eig3(const float A[3][3], float &lambda1, float &lambda2, Vec3 &prim_vec, Vec3 &sec_vec)
{
    // Fast power-iteration for largest eigenvalue + deflation for second.
    // Fall back to Eigen if something goes wrong.
    auto dot3 = [](const float a[3], const float b[3])
    {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    };
    auto mat_vec = [&](const float M[3][3], const float v[3], float out[3])
    {
        for (int r = 0; r < 3; ++r)
            out[r] = M[r][0] * v[0] + M[r][1] * v[1] + M[r][2] * v[2];
    };

    float M[3][3];
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            M[r][c] = A[r][c];

    const int MAX_IT = 40;
    const float TOL = 1e-10f;

    // First eigenpair
    float v[3] = {1.0f, 1.0f, 1.0f};
    float tmp[3];
    float nrm = std::sqrt(dot3(v, v));
    if (nrm == 0.0f)
    {
        v[0] = 1;
        v[1] = 0;
        v[2] = 0;
        nrm = 1.0f;
    }
    v[0] /= nrm;
    v[1] /= nrm;
    v[2] /= nrm;
    float lambda_prev = 0.0f;
    for (int it = 0; it < MAX_IT; ++it)
    {
        mat_vec(M, v, tmp);
        float tmpn = std::sqrt(dot3(tmp, tmp));
        if (tmpn == 0.0f)
            break;
        v[0] = tmp[0] / tmpn;
        v[1] = tmp[1] / tmpn;
        v[2] = tmp[2] / tmpn;
        mat_vec(M, v, tmp);
        float lambda = dot3(v, tmp);
        if (std::abs(lambda - lambda_prev) < TOL * std::max(1.0f, std::abs(lambda)))
        {
            lambda_prev = lambda;
            break;
        }
        lambda_prev = lambda;
    }

    lambda1 = lambda_prev;
    prim_vec = Vec3{v[0], v[1], v[2]};

    // Deflate and find second eigenvector (use original M to compute Rayleigh quotient)
    float M2[3][3];
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            M2[r][c] = M[r][c] - lambda1 * v[r] * v[c];

    float u[3] = {v[1] - v[2] + 1e-1f, v[2] - v[0] + 1e-1f, v[0] - v[1] + 1e-1f};
    nrm = std::sqrt(dot3(u, u));
    if (nrm == 0.0f)
    {
        u[0] = 1;
        u[1] = 0;
        u[2] = 0;
        nrm = 1.0f;
    }
    u[0] /= nrm;
    u[1] /= nrm;
    u[2] /= nrm;
    float lambda2_prev = 0.0f;
    for (int it = 0; it < MAX_IT; ++it)
    {
        mat_vec(M2, u, tmp);
        float tmpn = std::sqrt(dot3(tmp, tmp));
        if (tmpn == 0.0f)
            break;
        u[0] = tmp[0] / tmpn;
        u[1] = tmp[1] / tmpn;
        u[2] = tmp[2] / tmpn;
        mat_vec(M, u, tmp); // original matrix for Rayleigh
        float lambda = dot3(u, tmp);
        if (std::abs(lambda - lambda2_prev) < TOL * std::max(1.0f, std::abs(lambda)))
        {
            lambda2_prev = lambda;
            break;
        }
        lambda2_prev = lambda;
    }
    lambda2 = lambda2_prev;
    sec_vec = Vec3{u[0], u[1], u[2]};

    // Ordering and safety
    // if (!std::isfinite(lambda1) || !std::isfinite(lambda2) || lambda2 > lambda1 + 1e-12)
    // {
    //     // fallback to robust Eigen solver
    //     Eigen::Matrix3d E;
    //     E << A[0][0], A[0][1], A[0][2],
    //         A[1][0], A[1][1], A[1][2],
    //         A[2][0], A[2][1], A[2][2];
    //     Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> es;
    //     es.compute(E);
    //     if (es.info() == Eigen::Success)
    //     {
    //         Eigen::Vector3d w = es.eigenvalues(); // ascending
    //         lambda1 = w[2];
    //         lambda2 = w[1];
    //     }
    //     else
    //     {
    //         lambda1 = lambda2 = 0.0;
    //     }
    // }
};

// A hash function for our Vec3 struct, enabling it to be used as a key
// in std::unordered_map.
struct Vec3Hash
{
    std::size_t operator()(const Vec3 &v) const
    {
        // A common way to combine hashes of multiple integer members.
        // The prime numbers are used to reduce collisions.
        const std::size_t p1 = 73856093;
        const std::size_t p2 = 19349663;
        const std::size_t p3 = 83492791;

        return (static_cast<std::size_t>(v.x) * p1) ^
               (static_cast<std::size_t>(v.y) * p2) ^
               (static_cast<std::size_t>(v.z) * p3);
    }
};

auto compute_cov(const std::vector<uint32_t> &idxs, const Vec3 *verts, float cov[3][3])
{
    const size_t n = idxs.size();
    float mean[3] = {0.0f, 0.0f, 0.0f};
    for (uint32_t id : idxs)
    {
        const Vec3 &p = verts[id];
        mean[0] += p.x;
        mean[1] += p.y;
        mean[2] += p.z;
    }
    mean[0] /= n;
    mean[1] /= n;
    mean[2] /= n;
    // zero cov
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            cov[r][c] = 0.0;
    for (uint32_t id : idxs)
    {
        const Vec3 &p = verts[id];
        float d0 = p.x - mean[0];
        float d1 = p.y - mean[1];
        float d2 = p.z - mean[2];
        cov[0][0] += d0 * d0;
        cov[0][1] += d0 * d1;
        cov[0][2] += d0 * d2;
        cov[1][0] += d1 * d0;
        cov[1][1] += d1 * d1;
        cov[1][2] += d1 * d2;
        cov[2][0] += d2 * d0;
        cov[2][1] += d2 * d1;
        cov[2][2] += d2 * d2;
    }
    // Normalize by n
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            cov[r][c] /= static_cast<double>(n);
};

struct VoxelData
{
    std::vector<uint32_t> vertex_indices;
    Vec3 facing;
    Vec3 dir;
};

Vec3 get_voxel_coord(const Vec3 &point)
{
    return Vec3{
        std::floor(point.x / 0.03f),
        std::floor(point.y / 0.03f),
        std::floor(point.z / 0.03f)};
}

std::vector<bool> select_wire_verts(const Vec3 *verts, const Vec3 *vert_norms, uint32_t vertCount, const std::vector<std::vector<uint32_t>> &adj_verts, const std::vector<Vec3> &voxel_guesses, std::unordered_map<Vec3, VoxelData, Vec3Hash> &voxel_map)
{
    if (!verts || vertCount == 0 || !vert_norms || adj_verts.empty() || voxel_map.empty() || voxel_guesses.empty())
        return std::vector<bool>(vertCount, false);

    // Convert voxel guesses to vertex indices
    std::vector<uint32_t> vertex_guess_indices;
    uint32_t guessed_vertex_count = 0;
    for (const Vec3 &voxel_guess : voxel_guesses)
    {
        guessed_vertex_count += voxel_map.at(voxel_guess).vertex_indices.size();
    }

    if (guessed_vertex_count < vertCount / 6)
    {
        for (const Vec3 &voxel_guess : voxel_guesses)
        {
            auto local_vertex_guess_indices = voxel_map.at(voxel_guess).vertex_indices;
            for (const auto &index : local_vertex_guess_indices)
                vertex_guess_indices.push_back(index);
        }
    }

    std::vector<bool> is_wire(vertCount, false);
    std::stack<uint32_t> boundary;
    for (const uint32_t &guess : vertex_guess_indices)
    {
        is_wire[guess] = true;
        boundary.push(guess);
    }

    Vec3 prev_dir = voxel_map.at(voxel_guesses[0]).dir;
    std::vector<bool> visited(vertCount, false);
    while (!boundary.empty())
    {
        uint32_t current = boundary.top();
        boundary.pop();
        visited[current] = true;
        auto new_dir = voxel_map.at(get_voxel_coord(verts[current])).dir;

        bool is_good_voxel = new_dir.dot(prev_dir) > 0.0f;

        for (const auto &neighbor : adj_verts[current])
        {
            if (!is_wire[neighbor] && !visited[neighbor] && (is_good_voxel || vert_norms[neighbor].dot(prev_dir) < 0.3f))
            {
                is_wire[neighbor] = true;
                boundary.push(neighbor);
            }
        }

        

        if (is_good_voxel)
        {
            prev_dir = new_dir;
        }
    }

    uint32_t wire_count = 0;
    for (uint32_t i = 0; i < is_wire.size(); ++i)
    {
        if (is_wire[i])
        {
            printf("%i ", i);
            wire_count++;
        }
    }

    std::cout << "Number of wire vertices: " << wire_count << std::endl;

    return is_wire;
}

void build_adj_vertices(const uVec2i *edges, uint32_t edgeCount, std::vector<std::vector<uint32_t>> &out_adj_verts)
{
    if (!edges || edgeCount == 0)
        return;

    // Build adjacency list
    std::vector<uint32_t> degrees(out_adj_verts.size(), 0);
    for (uint32_t i = 0; i < edgeCount; ++i)
    {
        const uVec2i &e = edges[i];
        degrees[e.x]++;
        degrees[e.y]++;
    }

    // --- Reserve memory for each adjacency list ---
    for (uint32_t i = 0; i < out_adj_verts.size(); ++i)
    {
        out_adj_verts[i].reserve(degrees[i]);
    }

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





std::unordered_map<Vec3, VoxelData, Vec3Hash> build_voxel_map(const Vec3 *verts, uint32_t vertCount)
{
    std::unordered_map<Vec3, VoxelData, Vec3Hash> voxel_map;

    if (!verts || vertCount == 0)
        return voxel_map;

    for (uint32_t i = 0; i < vertCount; ++i)
    {
        const Vec3 &p = verts[i];
        Vec3 voxel_coord = get_voxel_coord(p);
        voxel_map[voxel_coord].vertex_indices.push_back(i);
    }

    return voxel_map;
}

void calculate_voxel_map_stats(std::unordered_map<Vec3, VoxelData, Vec3Hash> &voxel_map, const Vec3 *norms, const Vec3 *verts, std::vector<Vec3> &wire_guesses)
{
    for (auto &[voxel_coord, voxel_data] : voxel_map)
    {
        Vec3 avg_facing = {0, 0, 0};
        for (const auto &i : voxel_data.vertex_indices)
        {
            avg_facing = avg_facing + norms[i];
        }
        avg_facing = avg_facing / voxel_data.vertex_indices.size();

        float cov[3][3];
        compute_cov(voxel_data.vertex_indices, verts, cov);

        float lambda1, lambda2;
        Vec3 prim_vec, sec_vec;
        eig3(cov, lambda1, lambda2, prim_vec, sec_vec);

        voxel_data.facing = avg_facing;
        voxel_data.dir = prim_vec;

        std::vector<Vec3> neighbor_dirs = {{0, 0, 1}, {0, 1, 0}, {1, 0, 0}, {0, 0, -1}, {0, -1, 0}, {-1, 0, 0}};

        uint8_t neighbor_voxels = 0;

        for (const auto &dir : neighbor_dirs)
        {
            Vec3 neighbor_coord = voxel_coord + dir;
            if (voxel_map.find(neighbor_coord) != voxel_map.end())
            {
                neighbor_voxels++;
            }
        }
        // 0.3, 0.9
        if (avg_facing.length() < 0.25 && lambda1 / (lambda1 + lambda2) > 0.9f && neighbor_voxels <= 3)
        {
            wire_guesses.push_back(voxel_coord);
        }
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

    auto voxel_map = build_voxel_map(verts, vertCount);

    std::vector<Vec3> voxel_guesses;
    calculate_voxel_map_stats(voxel_map, vert_norms, (Vec3 *)verts, voxel_guesses);

    

    auto is_wire = select_wire_verts(verts, vert_norms, vertCount, adj_verts, voxel_guesses, voxel_map);

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    std::cout << "Time: " << duration.count() << " ms" << std::endl;

    std::vector<Vec2> hull = convex_hull_2D(verts, vertCount, is_wire);
    std::vector<float> angles = get_edge_angles_2D(hull);

    BoundingBox2D best_box;

    std::vector<Vec2> rot_hull;
    rot_hull.resize(hull.size());

    for (float angle : angles)
    {
        rotate_points_2D(hull, -angle, rot_hull);
        BoundingBox2D box = compute_aabb_2D(rot_hull, -angle);

        if (box.area < best_box.area)
        {
            best_box = box;
        }
    }
    *out_rot = {0, 0, best_box.rotation_angle};
    *out_trans = {0, 0, 0};
    return;
}