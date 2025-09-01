#pragma once

#include "vec.h"
#include "geo2d.h"

#include <vector>
#include <cstdint>

std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3>& verts, BoundingBox3D full_box);

struct SliceData {
    float area;
    Vec2 centroid;
    float mid_z;
};

struct COGResult {
    Vec3 overall_cog;
    std::vector<SliceData> slices;
};

COGResult calc_cog_volume_edges_intersections(const Vec3* verts,
                                              uint32_t vertCount,
                                              const uVec2i* edges,
                                              uint32_t edgeCount,
                                              BoundingBox3D full_box,
                                              float slice_height);
