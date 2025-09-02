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
    return monotonic_chain(verts, &Vec3::z, factor_to_coord(0.0f, full_box).z, factor_to_coord(0.05f, full_box).z);
}

// Compute the ratio of the full bounding box area to the base bounding box area
static inline float calc_ratio_full_to_base(const BoundingBox3D &full_box, const BoundingBox2D &base_box)
{
    if (base_box.area == 0)
        return 0;
    return (full_box.volume / (full_box.max_corner.z - full_box.min_corner.z)) / base_box.area;
}

static inline float get_min_cross_section(std::vector<SliceData> slices)
{
    float min_section = std::numeric_limits<float>::max();
    // Exclude top and bottom slices
    for (size_t i = 1; i < slices.size() - 1; ++i)
    {
        const auto &slice = slices[i];
        float section = slice.area;
        if (section < min_section)
            min_section = section;
    }
    return min_section;
}

bool is_ground(const std::vector<Vec3> &verts, COGResult &cog_result, BoundingBox3D full_box)
{
    if (cog_result.slices.empty())
        return false;

    float min_cross_section = get_min_cross_section(cog_result.slices);
    auto base_chull = calc_base_convex_hull(verts, full_box);
    float ratio = calc_ratio_full_to_base(full_box, compute_aabb_2D(base_chull));

    bool base_large_enough = ratio < 4.0f;
    bool is_thick_enough = min_cross_section > 15e-5f;
    bool cog_over_base = is_point_inside_polygon_2D(cog_result.overall_cog, base_chull);

    std::cout << "Base large enough: " << base_large_enough << std::endl;
    std::cout << "COG over base: " << cog_over_base << std::endl;
    std::cout << "Thick enough: " << is_thick_enough << std::endl;

    return base_large_enough && cog_over_base && is_thick_enough;
}

bool snapStandToYN(COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis)
{
    if (cog_result.slices.empty())
        return false;

    uint8_t count = 0;
    Vec2 avg_cog = {0, 0};

    // Exclude top and bottom slices
    for (size_t i = 1; i < cog_result.slices.size() - 1; ++i)
    {
        const auto &slice = cog_result.slices[i];
        if (full_box.area / slice.box.area > 5)
        {
            count++;
            avg_cog += slice.centroid;
        }
    }

    if (count == 0)
        return false;

    if (count > 1) {
        avg_cog /= static_cast<float>(count);
        avg_cog -= cog_result.overall_cog;
        front_axis += get_most_similar_axis(avg_cog) + 2;
    }


    return count > 1;
}

bool snapDenseToYN( COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis)
{
    if (cog_result.slices.empty())
        return false;

    Vec3 relative_cog = cog_result.overall_cog - Vec2{(full_box.min_corner.x + full_box.max_corner.x) * 0.5f, (full_box.min_corner.y + full_box.max_corner.y) * 0.5f};

    front_axis += get_most_similar_axis(relative_cog) + 2;

    return true;
}
