#pragma once

#include "share/vec.h"
#include "share/concepts.h"

#include <vector>
#include <algorithm>
#include <iostream>
#include <cmath>
#include <share/quaternion.h>

template <HasXY V>
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

inline Vec3 rotate_vertex_3D(const Vec3 &v, const Vec3 &euler) {
    float cx = std::cos(euler.x), sx = std::sin(euler.x);
    float cy = std::cos(euler.y), sy = std::sin(euler.y);
    float cz = std::cos(euler.z), sz = std::sin(euler.z);

    return {
        // New X
        v.x * (cy * cz) + v.y * (sx * sy * cz - cx * sz) + v.z * (cx * sy * cz + sx * sz),
        // New Y
        v.x * (cy * sz) + v.y * (sx * sy * sz + cx * cz) + v.z * (cx * sy * sz - sx * cz),
        // New Z
        v.x * (-sy) + v.y * (sx * cy) + v.z * (cx * cy)
    };
}

inline Vec3 rotate_vertex_3D_quat(const Vec3 &v, const Quaternion &q) {
    
    float x2 = q.x * q.x;
    float y2 = q.y * q.y;
    float z2 = q.z * q.z;

    float xy = q.x * q.y;
    float xz = q.x * q.z;
    float yz = q.y * q.z;
    float wx = q.w * q.x;
    float wy = q.w * q.y;
    float wz = q.w * q.z;

    float new_x = v.x * (1.0f - 2.0f * (y2 + z2)) +
                  v.y * (2.0f * (xy - wz)) +
                  v.z * (2.0f * (xz + wy));

    float new_y = v.x * (2.0f * (xy + wz)) +
                  v.y * (1.0f - 2.0f * (x2 + z2)) +
                  v.z * (2.0f * (yz - wx));

    float new_z = v.x * (2.0f * (xz - wy)) +
                  v.y * (2.0f * (yz + wx)) +
                  v.z * (1.0f - 2.0f * (x2 + y2));

    return {new_x, new_y, new_z};
}

template <HasXY V>
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

template <HasXY V, HasXY U>
bool is_point_inside_polygon_2D(const V &point, const std::vector<U> &verts)
{
    if (verts.size() < 3)
    {
        return false; // Not a polygon
    }

    bool inside = false;
    size_t n = verts.size();
    for (size_t i = 0, j = n - 1; i < n; j = i++)
    {
        const U &a = verts[i];
        const U &b = verts[j];
        if ((a.y > point.y) != (b.y > point.y) &&
            (point.x < a.x + (b.x - a.x) * (point.y - a.y) / (b.y - a.y + 1e-8f)))
        {
            inside = !inside;
        }
    }
    return inside;
}

template <HasXY V>
uint8_t get_most_similar_axis(const V &v)
{
    float posX = v.x;
    float negX = -v.x;
    float posY = v.y;
    float negY = -v.y;

    // Find the maximum value among the four
    float maxVal = std::max({posX, negX, posY, negY});

    // Determine which one(s) have the max value; in case of tie, prioritize in order: posX, negX, posY, negY
    if (maxVal == posX)
    {
        // std::cout << "Axis: +X" << std::endl;
        return 1;
    }
    if (maxVal == negX)
    {
        // std::cout << "Axis: -X" << std::endl;
        return 3;
    }
    if (maxVal == posY)
    {
        // std::cout << "Axis: +Y" << std::endl;
        return 0;
    }
    // std::cout << "Axis: -Y" << std::endl;
    return 2; // Only if all others are less
}

