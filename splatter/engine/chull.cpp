#include "chull.h"
#include "util.h"
#include <iostream>
#include <cstdint>
#include <vector>
#include <algorithm>

void convex_hull_2D(const Vec3* verts, uint32_t vertCount, uint32_t* out_indices, uint32_t* out_count) {
    *out_count = 0;
    if (!verts || vertCount == 0 || !out_indices || !out_count) return;
    
    if (vertCount <= 3) {
        for (uint32_t i = 0; i < vertCount; ++i) {
            out_indices[i] = i;
        }
        *out_count = vertCount;
        return;
    }

    // Single, clean Andrew's monotone chain implementation
    struct PT { 
        float x, y; 
        uint32_t idx; 
        
        bool operator<(const PT &other) const {
            return x < other.x || (x == other.x && y < other.y);
        }
    };
    
    std::vector<PT> points;
    points.reserve(vertCount);
    for (uint32_t i = 0; i < vertCount; ++i) {
        points.emplace_back(PT{verts[i].x, verts[i].y, i});
    }

    // Sort once
    std::sort(points.begin(), points.end());

    // Inline cross product for speed
    auto cross = [](const PT& O, const PT& A, const PT& B) -> float {
        return (A.x - O.x) * (B.y - O.y) - (A.y - O.y) * (B.x - O.x);
    };

    std::vector<PT> hull;
    hull.reserve(vertCount);  // Pre-allocate worst case

    // Lower hull
    for (const PT& p : points) {
        while (hull.size() >= 2 && cross(hull[hull.size()-2], hull[hull.size()-1], p) <= 0) {
            hull.pop_back();
        }
        hull.push_back(p);
    }

    // Upper hull
    const size_t lower_size = hull.size();
    for (int i = points.size() - 2; i >= 0; --i) {
        const PT& p = points[i];
        while (hull.size() > lower_size && cross(hull[hull.size()-2], hull[hull.size()-1], p) <= 0) {
            hull.pop_back();
        }
        hull.push_back(p);
    }

    // Remove duplicate last point
    if (hull.size() > 1) hull.pop_back();

    // Copy results
    *out_count = static_cast<uint32_t>(hull.size());
    for (uint32_t i = 0; i < *out_count; ++i) {
        out_indices[i] = hull[i].idx;
    }
}