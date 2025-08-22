#pragma once

#include "util.h"

#include <cstdint>
#include <vector>

std::vector<Vec2> convex_hull_2D(const Vec3* verts, uint32_t vertCount, const std::vector<bool>& selection);