#pragma once

#include "share/vec.h"
#include "share/concepts.h"

#include <vector>

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


Vec3 factor_to_coord(float factor, BoundingBox3D box);
Vec2 factor_to_coord(float factor, BoundingBox2D box);
Vec2 get_bounding_box_origin(BoundingBox2D box);