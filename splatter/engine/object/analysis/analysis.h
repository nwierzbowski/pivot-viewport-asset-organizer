#pragma once

#include "share/vec.h"
#include "object/util/geo2d.h"
#include "object/computation/b_box.h"

#include <vector>
#include <cstdint>

std::vector<Vec2> calc_base_convex_hull(const std::vector<Vec3> &verts, BoundingBox3D full_box);


