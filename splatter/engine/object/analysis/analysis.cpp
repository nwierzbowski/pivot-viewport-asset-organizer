#include "object/analysis/analysis.h"

#include "share/vec.h"
#include "object/util/geo2d.h"
#include "object/computation/chull.h"

#include <vector>
#include <cstdint>
#include <iostream>

// Calculate the base convex hull from vertices projected onto the XY plane at a specific Z level
std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3> &verts, BoundingBox3D full_box)
{
    return monotonic_chain(verts, &Vec3::z, full_box.min_corner.z, full_box.min_corner.z + 0.001);
}

// Compute the ratio of the full bounding box area to the base bounding box area
float calc_ratio_full_to_base(const BoundingBox2D &full_box, const BoundingBox2D &base_box)
{
    if (base_box.area == 0)
        return 0;
    return full_box.area / base_box.area;
}


