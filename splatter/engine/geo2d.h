#pragma once

#include "vec.h"

#include <vector>
#include <concepts>

struct BoundingBox2D {
    Vec2 min_corner;
    Vec2 max_corner;
    float area;
    float rotation_angle;  // Radians

    BoundingBox2D() : area(std::numeric_limits<float>::max()), rotation_angle(0) {}
};

struct BoundingBox3D {
    Vec3 min_corner;
    Vec3 max_corner;
    float volume;
    float rotation_angle;  // Radians

    BoundingBox3D() : volume(0), rotation_angle(0) {}
};

template<class V>
concept HasXY = requires(V v) {
    { v.x } -> std::convertible_to<float>;
    { v.y } -> std::convertible_to<float>;
};


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

template<class V, class Pred>
inline BoundingBox2D compute_aabb_2D_impl(const std::vector<V>& points, Pred pred) {
    if (points.empty())
        return {};

    bool found = false;
    float min_x = 0, max_x = 0;
    float min_y = 0, max_y = 0;

    for (const V& p : points) {
        if (!pred(p)) continue;
        if (!found) {
            min_x = max_x = p.x;
            min_y = max_y = p.y;
            found = true;
        } else {
            if (p.x < min_x) min_x = p.x;
            if (p.x > max_x) max_x = p.x;
            if (p.y < min_y) min_y = p.y;
            if (p.y > max_y) max_y = p.y;
        }
    }
    if (!found) return {};

    BoundingBox2D box;
    box.min_corner = {min_x, min_y};
    box.max_corner = {max_x, max_y};
    box.area = (max_x - min_x) * (max_y - min_y);
    box.rotation_angle = 0;
    return box;
}

template<class V, class Pred>
inline BoundingBox3D compute_aabb_3D_impl(const std::vector<V>& points, Pred pred) {
    if (points.empty())
        return {};

    bool found = false;
    float min_x = 0, max_x = 0;
    float min_y = 0, max_y = 0;
    float min_z = 0, max_z = 0;

    for (const V& p : points) {
        if (!pred(p)) continue;
        if (!found) {
            min_x = max_x = p.x;
            min_y = max_y = p.y;
            min_z = max_z = p.z;
            found = true;
        } else {
            if (p.x < min_x) min_x = p.x;
            if (p.x > max_x) max_x = p.x;
            if (p.y < min_y) min_y = p.y;
            if (p.y > max_y) max_y = p.y;
            if (p.z < min_z) min_z = p.z;
            if (p.z > max_z) max_z = p.z;
        }
    }
    if (!found) return {};

    BoundingBox3D box;
    box.min_corner = {min_x, min_y, min_z};
    box.max_corner = {max_x, max_y, max_z};
    box.volume = (max_x - min_x) * (max_y - min_y) * (max_z - min_z);
    box.rotation_angle = 0;
    return box;
}

template<HasXY V>
BoundingBox2D compute_aabb_2D(const std::vector<V> &points, float V::*coord, float min_val, float max_val)
{
    return compute_aabb_2D_impl(points, [coord, min_val, max_val](const V& p) {
        return p.*coord >= min_val && p.*coord <= max_val;
    });
}

template<HasXY V>
BoundingBox3D compute_aabb_3D(const std::vector<V> &points, float V::*coord, float min_val, float max_val)
{
    return compute_aabb_3D_impl(points, [coord, min_val, max_val](const V& p) {
        return p.*coord >= min_val && p.*coord <= max_val;
    });
}

template<HasXY V>
BoundingBox2D compute_aabb_2D(const std::vector<V> &points)
{
    return compute_aabb_2D_impl(points, [](const V&) { return true; });
}

template<HasXY V>
BoundingBox3D compute_aabb_3D(const std::vector<V> &points)
{
    return compute_aabb_3D_impl(points, [](const V&) { return true; });
}

template<HasXY V>
std::vector<Vec2> monotonic_chain(const std::vector<V>& verts, float V::*coord, float min_val, float max_val) {
    std::vector<Vec2> points;
    points.reserve(verts.size());

    if (verts.empty()) return points;

    for (const V& v : verts) {
        if (v.*coord >= min_val && v.*coord <= max_val) {
            points.emplace_back(Vec2{v.x, v.y});
        }
    }

    if (points.size() <= 3) {
        return points;
    }

    // Inline cross product for speed
    auto cross = [](const Vec2& O, const Vec2& A, const Vec2& B) -> float {
        return (A.x - O.x) * (B.y - O.y) - (A.y - O.y) * (B.x - O.x);
    };

    std::vector<Vec2> hull;
    hull.reserve(verts.size());  // Pre-allocate worst case

    // Lower hull
    for (const Vec2& p : points) {
        while (hull.size() >= 2 && cross(hull[hull.size()-2], hull[hull.size()-1], p) <= 0) {
            hull.pop_back();
        }
        hull.push_back(p);
    }

    // Upper hull
    const size_t lower_size = hull.size();
    for (int i = points.size() - 2; i >= 0; --i) {
        const Vec2& p = points[i];
        while (hull.size() > lower_size && cross(hull[hull.size()-2], hull[hull.size()-1], p) <= 0) {
            hull.pop_back();
        }
        hull.push_back(p);
    }

    // Remove duplicate last point
    if (hull.size() > 1) hull.pop_back();

    return hull;
}

template<HasXY V>
std::vector<Vec2> monotonic_chain(const std::vector<V>& verts)
{
    return monotonic_chain(verts, &V::x, -std::numeric_limits<float>::infinity(), std::numeric_limits<float>::infinity());
}

std::vector<float> get_edge_angles_2D(const std::vector<Vec2> &hull);