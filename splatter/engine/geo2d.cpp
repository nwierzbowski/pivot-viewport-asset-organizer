#include "geo2d.h"
#include "util.h"

#include <vector>
#include <cmath>
#include <algorithm>



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
            if (angle < 0)
                angle += M_PI;
            if (angle >= M_PI)
                angle -= M_PI;

            angles.push_back(angle);
        }
    }

    // De‑duplicate (quantize to ~1e-4 rad to avoid FP noise)
    std::sort(angles.begin(), angles.end());
    auto last = std::unique(angles.begin(), angles.end(),
                            [](float a, float b)
                            { return std::abs(a - b) < 1e-4f; });
    angles.erase(last, angles.end());
    return angles;
}