#pragma once

#include "share/vec.h"
#include "object/computation/b_box.h"

#include <vector>
#include <span>

struct SliceData
{
    float area;
    BoundingBox2D box;
    Vec2 centroid;
    float mid_z;
};

struct COGResult
{
    Vec3 overall_cog;
    std::vector<SliceData> slices;
};

COGResult calc_cog_volume_edges_intersections(std::span<const Vec3> verts,
                                              std::span<const uVec2i> edges,
                                              BoundingBox3D full_box,
                                              float slice_height);