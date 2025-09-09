#pragma once

#include "share/vec.h"
#include "object/computation/b_box.h"
#include "object/computation/cog.h"

#include <vector>

bool is_ground(const std::vector<Vec3> &verts, COGResult &cog_result, BoundingBox3D full_box);

bool snapStandToYN(COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis);

bool snapHighToYN(COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis);

bool snapDenseToYN(COGResult &cog_result, BoundingBox2D full_box, uint8_t &front_axis, const std::vector<uint8_t> &axis_options = {});

bool isSmall(BoundingBox3D full_box);

bool isSquarish(BoundingBox3D full_box);

void alignLongAxisToX(BoundingBox3D &full_box,  uint8_t &front_axis);