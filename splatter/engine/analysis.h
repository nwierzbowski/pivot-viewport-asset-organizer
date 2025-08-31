#pragma once

#include "vec.h"
#include "geo2d.h"

#include <vector>
#include <cstdint>

std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3>& verts, BoundingBox3D full_box);

Vec3 calc_cog_volume(const Vec3* verts, uint32_t vertCount, const std::vector<std::vector<uint32_t>> &adj_verts, BoundingBox3D full_box);
