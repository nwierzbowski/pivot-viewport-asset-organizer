#pragma once

#include "util.h"

#include <cstdint>

void align_min_bounds(const Vec3* verts, uint32_t vertCount, const uVec3i* faces, uint32_t faceCount, Vec3* out_rot, Vec3* out_trans);
