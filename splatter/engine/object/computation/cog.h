#pragma once

#include "share/vec.h"
#include "object/computation/b_box.h"

#include <vector>

struct SliceData
{
    float area;
    Vec2 centroid;
    float mid_z;
};

struct COGResult
{
    Vec3 overall_cog;
    std::vector<SliceData> slices;
};

COGResult calc_cog_volume_edges_intersections(const Vec3 *verts,
                                              uint32_t vertCount,
                                              const uVec2i *edges,
                                              uint32_t edgeCount,
                                              BoundingBox3D full_box,
                                              float slice_height);