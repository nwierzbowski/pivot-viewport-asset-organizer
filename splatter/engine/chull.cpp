#include "chull.h"
#include "util.h"
#include <cstdint>
#include <vector>
#include <algorithm>

std::vector<Vec2> convex_hull_2D(const Vec3* verts, uint32_t vertCount, const std::vector<bool>& selection) {
    std::vector<Vec2> points;
    points.reserve(vertCount);

    if (!verts || vertCount == 0) return points;

    for (uint32_t i = 0; i < vertCount; ++i) {
        if (!selection.empty() && !selection[i]) {
            points.emplace_back(Vec2{verts[i].x, verts[i].y});
        }
    }

    if (vertCount <= 3) {
        return points;
    }

    // Sort once
    std::sort(points.begin(), points.end());

    // Inline cross product for speed
    auto cross = [](const Vec2& O, const Vec2& A, const Vec2& B) -> float {
        return (A.x - O.x) * (B.y - O.y) - (A.y - O.y) * (B.x - O.x);
    };

    std::vector<Vec2> hull;
    hull.reserve(vertCount);  // Pre-allocate worst case

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