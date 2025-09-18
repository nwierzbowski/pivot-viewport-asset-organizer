#include "object/analysis/ground.h"

#include "share/vec.h"
#include "object/util/geo2d.h"
#include "object/computation/chull.h"
#include "object/computation/cog.h"

#include <vector>
#include <cstdint>
#include <cmath>

// Calculate the base convex hull from vertices projected onto the XY plane at a specific Z level
static inline std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3> &verts, BoundingBox3D full_box)
{
    return monotonic_chain(verts, &Vec3::z, factor_to_coord(0.0f, full_box).z, factor_to_coord(0.02f, full_box).z);
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
    float ratio = calc_ratio_full_to_base(full_box, cog_result.slices.front().box);

    bool base_large_enough = ratio < 4.0f;
    bool is_thick_enough = min_cross_section > 15e-5f;
    bool cog_over_base = is_point_inside_polygon_2D(cog_result.overall_cog, base_chull);

    std::cerr << "Base large enough: " << base_large_enough << std::endl;
    std::cerr << "COG over base: " << cog_over_base << std::endl;
    std::cerr << "Thick enough: " << is_thick_enough << std::endl;

    return base_large_enough && cog_over_base && is_thick_enough;
}

bool snapStandToYN(COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis)
{
    if (cog_result.slices.empty())
        return false;

    uint8_t count = 0;
    Vec2 avg_cog = {0, 0};

    // Exclude top and bottom slices
    for (size_t i = 1; i < cog_result.slices.size() / 2; ++i)
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

    if (count > 1)
    {
        avg_cog /= static_cast<float>(count);
        avg_cog -= cog_result.overall_cog;
        front_axis += get_most_similar_axis(avg_cog) + 2;
    }

    return count > 1;
}

bool snapHighToYN(COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis)
{
    if (cog_result.slices.empty())
        return false;

    Vec2 top_cog = cog_result.slices.back().centroid;

    Vec2 relative_cog = top_cog - get_bounding_box_origin(full_box);
    float fac = 0.05f;

    float x_fac = factor_to_coord(fac, full_box).x - factor_to_coord(0.0f, full_box).x;
    float y_fac = factor_to_coord(fac, full_box).y - factor_to_coord(0.0f, full_box).y;

    if (relative_cog.length() < std::max(x_fac, y_fac))
    {
        return false;
    }
    else
    {
        front_axis += get_most_similar_axis(relative_cog) + 2;
        return true;
    }
}

bool snapDenseToYN(COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis, const std::vector<uint8_t> &axis_options)
{
    if (cog_result.slices.empty())
        return false;

    Vec3 relative_cog = cog_result.overall_cog - Vec2{(full_box.min_corner.x + full_box.max_corner.x) * 0.5f, (full_box.min_corner.y + full_box.max_corner.y) * 0.5f};

    if (relative_cog.length() < 0.01f * std::max(full_box.max_corner.x - full_box.min_corner.x, full_box.max_corner.y - full_box.min_corner.y))
    {
        return false;
    }
    else
    {
        front_axis += get_most_similar_axis(relative_cog, axis_options) + 2;

        return true;
    }
}

bool isSmall(BoundingBox3D full_box)
{
    return full_box.volume < 0.05f;
}

bool isSquarish(BoundingBox3D full_box)
{
    float len_x = full_box.max_corner.x - full_box.min_corner.x;
    float len_y = full_box.max_corner.y - full_box.min_corner.y;

    float min_len = std::min({len_x, len_y});
    float max_len = std::max({len_x, len_y});

    if (min_len == 0)
        return false;

    return (max_len / min_len) < 2.0f;
}

void alignLongAxisToX(BoundingBox3D &full_box, uint8_t &front_axis)
{
    float len_x = full_box.max_corner.x - full_box.min_corner.x;
    float len_y = full_box.max_corner.y - full_box.min_corner.y;

    if (len_y > len_x)
    {
        front_axis += 1; // Rotate 90 degrees to align long axis with X
    }
}

static inline Vec2 get_max_axes_middle_slices(const COGResult &cog_result)
{
    if (cog_result.slices.empty())
        return {0.0f, 0.0f};

    size_t total_slices = cog_result.slices.size();
    size_t start_idx = total_slices / 4;
    size_t end_idx = 3 * total_slices / 4;

    float max_x = 0.0f;
    float max_y = 0.0f;

    for (size_t i = start_idx; i < end_idx; ++i)
    {
        const auto &slice = cog_result.slices[i];
        float x_extent = slice.box.max_corner.x - slice.box.min_corner.x;
        float y_extent = slice.box.max_corner.y - slice.box.min_corner.y;

        if (x_extent > max_x)
            max_x = x_extent;
        if (y_extent > max_y)
            max_y = y_extent;
    }

    return {max_x, max_y};
}

static inline Vec2 get_middle_slices_pos_neg_ratio(const std::vector<Vec3> &verts, const COGResult &cog_result, BoundingBox3D full_box)
{
    float total_height = full_box.max_corner.z - full_box.min_corner.z;
    float start_z = full_box.min_corner.z + total_height * 3 / 8;
    float end_z = full_box.min_corner.z + total_height;

    Vec2 center = {cog_result.overall_cog.x, cog_result.overall_cog.y};

    size_t pos_x = 0, neg_x = 0, pos_y = 0, neg_y = 0;

    for (const Vec3 &vert : verts) {
        if (vert.z >= start_z && vert.z < end_z) {
            float rel_x = vert.x - center.x;
            float rel_y = vert.y - center.y;
            if (rel_x > 0) pos_x++;
            else if (rel_x < 0) neg_x++;
            if (rel_y > 0) pos_y++;
            else if (rel_y < 0) neg_y++;
        }
    }

    float ratio_x = neg_x > 0 ? static_cast<float>(pos_x) / neg_x : (pos_x > 0 ? 10.0f : 0.0f);
    float ratio_y = neg_y > 0 ? static_cast<float>(pos_y) / neg_y : (pos_y > 0 ? 10.0f : 0.0f);

    return {ratio_x, ratio_y};
}

bool is_flat(const std::vector<Vec3> &verts, const COGResult &cog_result, BoundingBox3D full_box, uint8_t &front_axis)
{
    const Vec2 max_axes = get_max_axes_middle_slices(cog_result);
    const float min_len = std::min(max_axes.x, max_axes.y);
    const float max_len = std::max(max_axes.x, max_axes.y);

    if (min_len == 0.0f) {
        return false;
    }

    const Vec2 ratios = get_middle_slices_pos_neg_ratio(verts, cog_result, full_box);
    const float facing_ratio = (max_axes.y > max_axes.x) ? ratios.x : ratios.y;
    const uint8_t dir = (max_axes.y > max_axes.x) ? 3 : 2;

    const bool is_valid_shape = (max_len / min_len) > 2.5f;
    const bool is_valid_size = (min_len < 0.08f) && (max_len > 0.3f);

    if (is_valid_shape && is_valid_size) {
        front_axis = dir - 2 * static_cast<uint8_t>(facing_ratio > 1.0f);
        return true;
    }

    return false;
}
