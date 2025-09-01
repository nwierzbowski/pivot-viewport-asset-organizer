#include "wall.h"
#include "object/computation/b_box.h"

#include <vector>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>

struct Side
{
    float area;
    uint8_t axis;
};

static inline Side max_side_bbox_area(std::vector<Vec3> &verts, BoundingBox3D full_box)
{
    if (verts.empty())
        return {0.0f, 0};

    BoundingBox3D boxXP = compute_aabb_3D(verts, &Vec3::x, factor_to_coord(0.99, full_box).x, factor_to_coord(1.0, full_box).x);
    BoundingBox3D boxXN = compute_aabb_3D(verts, &Vec3::x, factor_to_coord(0.0, full_box).x, factor_to_coord(0.01, full_box).x);
    BoundingBox3D boxYP = compute_aabb_3D(verts, &Vec3::y, factor_to_coord(0.99, full_box).y, factor_to_coord(1.0, full_box).y);
    BoundingBox3D boxYN = compute_aabb_3D(verts, &Vec3::y, factor_to_coord(0.0, full_box).y, factor_to_coord(0.01, full_box).y);

    float boxXP_area = (boxXP.max_corner.x != boxXP.min_corner.x) ? boxXP.volume / (boxXP.max_corner.x - boxXP.min_corner.x) : 0.0f;
    float boxXN_area = (boxXN.max_corner.x != boxXN.min_corner.x) ? boxXN.volume / (boxXN.max_corner.x - boxXN.min_corner.x) : 0.0f;
    float boxYP_area = (boxYP.max_corner.y != boxYP.min_corner.y) ? boxYP.volume / (boxYP.max_corner.y - boxYP.min_corner.y) : 0.0f;
    float boxYN_area = (boxYN.max_corner.y != boxYN.min_corner.y) ? boxYN.volume / (boxYN.max_corner.y - boxYN.min_corner.y) : 0.0f;

    Side sides[4] = {
        {boxXP_area, 1},
        {boxXN_area, 3},
        {boxYP_area, 2},
        {boxYN_area, 0}};

    Side max_side = {0.0f, 0};
    for (const auto &side : sides)
    {
        if (side.area > max_side.area)
        {
            max_side = side;
        }
    }
    return max_side;
}

bool is_wall(std::vector<Vec3> &verts, BoundingBox3D full_box, uint8_t &front_axis_out)
{
    Side side = max_side_bbox_area(verts, full_box);


    float full_area = 0.0f;
    switch (side.axis)
    {
    case 0:
    case 2:
        full_area = (full_box.max_corner.x - full_box.min_corner.x) * (full_box.max_corner.z - full_box.min_corner.z);
        break;
    case 1:
    case 3:
        full_area = (full_box.max_corner.y - full_box.min_corner.y) * (full_box.max_corner.z - full_box.min_corner.z);
        break;
    }

    bool is_side_large_enough = (full_area / side.area) < 10.0f;

    front_axis_out += side.axis;

    return is_side_large_enough;
}