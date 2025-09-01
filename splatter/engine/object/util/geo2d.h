#pragma once

#include "share/vec.h"
#include "share/concepts.h"

#include <vector>
#include <algorithm>

template<HasXY V>
void rotate_points_2D(const std::vector<V> &points, float angle, std::vector<V> &out)
{
    if (out.size() != points.size())
        out.resize(points.size());

    float c = std::cos(angle);
    float s = std::sin(angle);

    for (size_t i = 0; i < points.size(); ++i)
    {
        // Cache originals so in-place rotation works
        float ox = points[i].x;
        float oy = points[i].y;
        out[i].x = ox * c - oy * s;
        out[i].y = ox * s + oy * c;
        // Preserve extra components (e.g. z) if present
        if constexpr (requires { points[i].z; })
            out[i].z = points[i].z;
    }
}

template<HasXY V>
std::vector<float> get_edge_angles_2D(const std::vector<V> &verts)
{
    std::vector<float> angles;
    angles.reserve(verts.size());

    for (size_t i = 0; i < verts.size(); ++i)
    {
        size_t next = (i + 1) % verts.size();
        Vec2 edge = verts[next] - verts[i];

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

template<HasXY V, HasXY U>
bool is_point_inside_polygon_2D(const V& point, const std::vector<U>& verts) {
    if (verts.size() < 3) return false; // Not a polygon

    bool inside = false;
    size_t n = verts.size();
    for (size_t i = 0, j = n - 1; i < n; j = i++) {
        const U& a = verts[i];
        const U& b = verts[j];
        if ((a.y > point.y) != (b.y > point.y) &&
            (point.x < a.x + (b.x - a.x) * (point.y - a.y) / (b.y - a.y + 1e-8f))) {
            inside = !inside;
        }
    }
    return inside;
}