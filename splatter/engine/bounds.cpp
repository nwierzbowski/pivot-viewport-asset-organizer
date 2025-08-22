#include "bounds.h"
#include "util.h"
#include "chull.h"

#include <iostream>
#include <cstdint>
#include <vector>
#include <cmath>
#include <algorithm>
#include <queue>

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

std::vector<bool> elim_wires(const Vec3 *verts, uint32_t vertCount, const std::vector<std::vector<uint32_t>> &adj_verts)
{
    if (!verts || vertCount == 0)
        return std::vector<bool>(vertCount, false);

    // Parameters
    const uint32_t K = std::min<uint32_t>(100, vertCount); // neighborhood size
    const float LINEARITY_THRESHOLD = 0.95f;
    const int MAX_POWER_ITERS = 50;
    const float POWER_TOL = 1e-6f;
    const uint8_t MIN_WIRE_GROUP_SIZE = 10;

    // auto sq = [](float x){ return x*x; };

    // Helper: compute covariance matrix (3x3) for a set of points given their indices
    auto compute_cov = [&](const std::vector<uint32_t> &idxs, double cov[3][3])
    {
        const size_t n = idxs.size();
        double mean[3] = {0.0, 0.0, 0.0};
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
            double d0 = p.x - mean[0];
            double d1 = p.y - mean[1];
            double d2 = p.z - mean[2];
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

    // Helper: power iteration to get largest eigenvalue & eigenvector of symmetric 3x3 matrix
    auto power_iteration = [&](const double A[3][3], double &out_eigenvalue, double out_vec[3])
    {
        double x[3] = {1.0, 1.0, 1.0};
        // normalize
        double norm = std::sqrt(x[0] * x[0] + x[1] * x[1] + x[2] * x[2]);
        for (int i = 0; i < 3; ++i)
            x[i] /= (norm > 0 ? norm : 1.0);
        double prev_lambda = 0.0;
        for (int iter = 0; iter < MAX_POWER_ITERS; ++iter)
        {
            double y[3] = {0.0, 0.0, 0.0};
            for (int r = 0; r < 3; ++r)
                for (int c = 0; c < 3; ++c)
                    y[r] += A[r][c] * x[c];
            double ynorm = std::sqrt(y[0] * y[0] + y[1] * y[1] + y[2] * y[2]);
            if (ynorm == 0.0)
            {
                out_eigenvalue = 0.0;
                out_vec[0] = out_vec[1] = out_vec[2] = 0.0;
                return;
            }
            for (int i = 0; i < 3; ++i)
                x[i] = y[i] / ynorm;
            // Rayleigh quotient
            double lambda = 0.0;
            for (int r = 0; r < 3; ++r)
                for (int c = 0; c < 3; ++c)
                    lambda += x[r] * A[r][c] * x[c];
            if (std::abs(lambda - prev_lambda) < POWER_TOL)
                break;
            prev_lambda = lambda;
        }
        out_eigenvalue = 0.0;
        for (int r = 0; r < 3; ++r)
            for (int c = 0; c < 3; ++c)
                out_eigenvalue += x[r] * A[r][c] * x[c];
        out_vec[0] = x[0];
        out_vec[1] = x[1];
        out_vec[2] = x[2];
    };

    std::vector<uint32_t> neighbor_idxs;
    neighbor_idxs.reserve(K);

    std::vector<int> is_wire(vertCount, 0);
    std::vector<float> linearity_scores(vertCount, 0.0f);

    for (uint32_t i = 0; i < vertCount; ++i)
    {
        const Vec3 &pi = verts[i];

        // Use a min-heap of (squared distance, index). Track which nodes were pushed to avoid duplicates.
        std::priority_queue<std::pair<double, uint32_t>,
                            std::vector<std::pair<double, uint32_t>>,
                            std::greater<std::pair<double, uint32_t>>> pq2;

        std::vector<char> pushed(vertCount, 0);
        auto push_if = [&](uint32_t idx) {
            if (idx == i || pushed[idx]) return;
            double dx = verts[idx].x - pi.x;
            double dy = verts[idx].y - pi.y;
            double dz = verts[idx].z - pi.z;
            double d2 = dx*dx + dy*dy + dz*dz;
            pq2.emplace(d2, idx);
            pushed[idx] = 1;
        };

        // seed with immediate neighbors
        for (uint32_t neighbor_idx : adj_verts[i]) {
            push_if(neighbor_idx);
        }

        neighbor_idxs.clear();

        // collect up to K unique closest indices (graph-expanded)
        while (neighbor_idxs.size() < K && !pq2.empty())
        {
            auto top = pq2.top();
            pq2.pop();
            uint32_t current_idx = top.second;

            // add to result
            neighbor_idxs.push_back(current_idx);

            // expand from this node
            for (uint32_t neighbor_idx : adj_verts[current_idx])
            {
                push_if(neighbor_idx);
            }
        }

        // ensure we have at least one index (avoid empty neighborhood)
        if (neighbor_idxs.empty())
            neighbor_idxs.push_back(i);
        // for (uint32_t j = 0; j < vertCount; ++j)
        // {
        //     double dx = pi.x - verts[j].x;
        //     double dy = pi.y - verts[j].y;
        //     double dz = pi.z - verts[j].z;
        //     double dsq = dx * dx + dy * dy + dz * dz;
        //     dists.push_back({dsq, j});
        // }
        // std::nth_element(dists.begin(), dists.begin() + (K - 1), dists.end(),
        //                  [](const DistIdx &a, const DistIdx &b)
        //                  { return a.d < b.d; });
        // neighbor_idxs.clear();
        // for (uint32_t t = 0; t < K; ++t)
        //     neighbor_idxs.push_back(dists[t].idx);

        // compute covariance
        double cov[3][3];
        compute_cov(neighbor_idxs, cov);

        // compute eigenvalues: largest via power iteration
        double lambda1, v1[3];
        power_iteration(cov, lambda1, v1);

        // deflate to get second eigenvalue: A' = A - lambda1 * v1 v1^T
        double A_defl[3][3];
        for (int r = 0; r < 3; ++r)
            for (int c = 0; c < 3; ++c)
                A_defl[r][c] = cov[r][c] - lambda1 * v1[r] * v1[c];

        double lambda2, v2[3];
        power_iteration(A_defl, lambda2, v2);

        // trace gives sum eigenvalues; compute lambda3
        double trace = cov[0][0] + cov[1][1] + cov[2][2];
        double lambda3 = trace - lambda1 - lambda2;
        if (lambda3 < 0)
            lambda3 = 0.0; // numeric safety

        double lin = 0.0;
        if (lambda1 > 0.0)
            lin = static_cast<double>(lambda1 - lambda2) / static_cast<double>(lambda1);
        linearity_scores[i] = static_cast<float>(lin);
        if (lin > LINEARITY_THRESHOLD)
            is_wire[i] = 1;
    }

    std::vector<bool> final_is_wire(vertCount, false);
    std::vector<bool> visited(vertCount, false);
    std::vector<int> boundary_indices;

    // Populate final_is_wire
    for (uint32_t i = 0; i < vertCount; ++i)
    {
        if (is_wire[i] && visited[i] == false)
        {
            std::vector<uint32_t> group;
            std::queue<uint32_t> queue;
            std::vector<uint32_t> current_bounds;
            queue.push(i);
            visited[i] = true;
            while (!queue.empty())
            {
                uint32_t idx = queue.front();
                queue.pop();
                group.push_back(idx);

                // Check neighbors
                for (uint32_t neighbor : adj_verts[idx])
                {
                    if (is_wire[neighbor] && !visited[neighbor])
                    {
                        visited[neighbor] = true;
                        queue.push(neighbor);
                    }
                    else if (!is_wire[neighbor] && std::find(current_bounds.begin(), current_bounds.end(), neighbor) == current_bounds.end())
                    {
                        current_bounds.push_back(neighbor);
                    }
                }
            }

            // If group is large enough, mark all as wire
            if (group.size() >= MIN_WIRE_GROUP_SIZE)
            {
                for (uint32_t idx : group)
                {
                    final_is_wire[idx] = true;
                }
                for (uint32_t idx : current_bounds)
                {
                    boundary_indices.push_back(idx);
                }
            }
        }
    }

    std::queue<uint32_t> queue;
    for (uint32_t idx : boundary_indices)
    {
        queue.push(idx);
        // std::cout << "Pushing starting bounds: " << idx << std::endl;
    }

    while (!queue.empty())
    {
        uint32_t current = queue.front();
        queue.pop();

        if (linearity_scores[current] > 0.5)
        {

            final_is_wire[current] = true;
            // Check neighbors
            for (uint32_t neighbor : adj_verts[current])
            {
                if (!final_is_wire[neighbor])
                {
                    queue.push(neighbor);
                }
            }
        }
    }
    return final_is_wire;

    // NOTE:
    // - This function currently only classifies and reports wire-like points.
    // - To actually remove them or return indices, change the API (e.g. return a vector<uint32_t>
    //   of wire indices) or provide out parameters. Consider implementing seed-and-grow
    //   region expansion on high-confidence seeds (higher threshold) to make a robust removal.
}

void build_adj_vertices(const Vec3 *verts, uint32_t vertCount, const Vec3i *faces, uint32_t faceCount, std::vector<std::vector<uint32_t>> &out_adj_verts)
{
    if (!verts || vertCount == 0 || !faces || faceCount == 0)
        return;

    // Build adjacency list
    for (uint32_t i = 0; i < faceCount; ++i)
    {
        const Vec3i &f = faces[i];
        if (f.x < vertCount && f.y < vertCount)
        {
            out_adj_verts[f.x].push_back(f.y);
            out_adj_verts[f.y].push_back(f.x);
        }
        if (f.y < vertCount && f.z < vertCount)
        {
            out_adj_verts[f.y].push_back(f.z);
            out_adj_verts[f.z].push_back(f.y);
        }
        if (f.z < vertCount && f.x < vertCount)
        {
            out_adj_verts[f.z].push_back(f.x);
            out_adj_verts[f.x].push_back(f.z);
        }
    }

    // Remove duplicates and sort each adjacency list
    for (auto &neighbors : out_adj_verts)
    {
        std::sort(neighbors.begin(), neighbors.end());
        neighbors.erase(std::unique(neighbors.begin(), neighbors.end()), neighbors.end());
    }
}

void align_min_bounds(const Vec3 *verts, uint32_t vertCount, const Vec3i *faces, uint32_t faceCount, Vec3 *out_rot, Vec3 *out_trans)
{
    if (!verts || vertCount == 0 || !faces || faceCount == 0 || !out_rot || !out_trans)
        return;

    if (vertCount == 1)
    {
        *out_rot = {0, 0, 0};
        *out_trans = {verts[0].x, verts[0].y, verts[0].z};
        return;
    }

    // Calculate vertex adjacency lists
    std::vector<std::vector<uint32_t>> adj_verts(vertCount);
    build_adj_vertices(verts, vertCount, faces, faceCount, adj_verts);

    auto is_wire = elim_wires(verts, vertCount, adj_verts);

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