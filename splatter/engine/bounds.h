#pragma once

#include "util.h"

#include <cstdint>

void align_min_bounds(const Vec3* verts, const Vec3* vert_norms, uint32_t vertCount, const uVec2i* edges, uint32_t edgeCount, Vec3* out_rot, Vec3* out_trans);
