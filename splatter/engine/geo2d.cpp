#include "geo2d.h"
#include "vec.h"

#include <vector>
#include <cmath>
#include <algorithm>
#include <concepts>


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