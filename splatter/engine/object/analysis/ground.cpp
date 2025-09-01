#include "object/analysis/ground.h"

#include "share/vec.h"
#include "object/util/geo2d.h"
#include "object/computation/chull.h"
#include "object/computation/cog.h"

#include <vector>
#include <cstdint>

// Calculate the base convex hull from vertices projected onto the XY plane at a specific Z level
static inline std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3> &verts, BoundingBox3D full_box)
{
    return monotonic_chain(verts, &Vec3::z, full_box.min_corner.z, full_box.min_corner.z + 0.001);
}

// Compute the ratio of the full bounding box area to the base bounding box area
static inline float calc_ratio_full_to_base(const BoundingBox3D &full_box, const BoundingBox2D &base_box)
{
    if (base_box.area == 0)
        return 0;
    return full_box.volume / (full_box.max_corner.z - full_box.min_corner.z) / base_box.area;
}

static inline float get_min_cross_section(std::vector<SliceData> slices)
{
    float min_section = std::numeric_limits<float>::max();
    for (const auto &slice : slices)
    {
        float section = slice.area;
        if (section < min_section)
            min_section = section;
    }
    return min_section;
}

bool is_ground(const std::vector<Vec3> &verts, Vec3 cog, BoundingBox3D full_box, BoundingBox2D base_box, std::vector<SliceData> slices)
{
    if (slices.empty())
        return false;

    float min_cross_section = get_min_cross_section(slices);
    float ratio = calc_ratio_full_to_base(full_box, base_box);
    auto base_chull = calc_base_convex_hull(verts, full_box);

    bool base_too_small = ratio < 4.0f;
    bool is_too_thin = min_cross_section < 25e-5f;
    bool cog_over_base = is_point_inside_polygon_2D(cog, base_chull);

    return !base_too_small && !is_too_thin && cog_over_base;
}


