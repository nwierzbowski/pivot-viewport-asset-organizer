#pragma once

#include "share/vec.h"
#include "share/concepts.h"

#include <vector>
#include <concepts>

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