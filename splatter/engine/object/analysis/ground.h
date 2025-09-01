#pragma once

#include "share/vec.h"
#include "object/computation/b_box.h"
#include "object/computation/cog.h"

#include <vector>

bool is_ground(const std::vector<Vec3> &verts, Vec3 cog, BoundingBox3D full_box, BoundingBox2D base_box, std::vector<SliceData> slices);

