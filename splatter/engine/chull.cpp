#include "chull.h"

#include "util.h"

#include <iostream>
#include <cstdint>
#include <vector>
#include <algorithm>


void say_hello_from_cpp() {
    std::cout << "Hello from the C++ Engine! Recomp" << std::endl;
}

void convex_hull_2D(const Vec3* verts, uint32_t vertCount, uint32_t* out_indices, uint32_t* out_count) {
    // Monotone chain convex hull in XY, returning indices into the input array
    struct PT { float x, y; uint32_t idx; };
    *out_count = 0;
    if (!verts || vertCount == 0 || !out_indices || !out_count) return;
    if (vertCount == 1) {
        out_indices[0] = 0;
        *out_count = 1;
        return;
    }

    std::vector<PT> P;
    P.reserve(vertCount);
    for (uint32_t i = 0; i < vertCount; ++i) {
        P.push_back(PT{verts[i].x, verts[i].y, i});
    }

    std::sort(P.begin(), P.end(), [](const PT& a, const PT& b) {
        if (a.x == b.x) return a.y < b.y;
        return a.x < b.x;
    });

    auto cross = [](const PT& O, const PT& A, const PT& B) {
        // cross((A - O), (B - O))
        return (A.x - O.x) * (B.y - O.y) - (A.y - O.y) * (B.x - O.x);
    };

    std::vector<PT> H;
    H.reserve(2 * P.size());

    // Lower hull
    for (const auto& pt : P) {
        while (H.size() >= 2 && cross(H[H.size() - 2], H.back(), pt) <= 0.0f) {
            H.pop_back();
        }
        H.push_back(pt);
    }
    // Upper hull
    size_t lower_size = H.size();
    for (int i = (int)P.size() - 2; i >= 0; --i) {
        const auto& pt = P[(size_t)i];
        while (H.size() > lower_size && cross(H[H.size() - 2], H.back(), pt) <= 0.0f) {
            H.pop_back();
        }
        H.push_back(pt);
    }

    if (!H.empty()) {
        H.pop_back(); // last point is same as first
    }

    uint32_t n = (uint32_t)H.size();
    for (uint32_t i = 0; i < n; ++i) {
        out_indices[i] = H[i].idx;
    }
    *out_count = n;
}