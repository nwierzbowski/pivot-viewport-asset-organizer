#pragma once

#include "vec.h"

#include <vector>

void compute_cov(const std::vector<uint32_t> &idxs, const Vec3 *verts, float cov[3][3]);

void eig3(const float A[3][3], float &lambda1, float &lambda2, Vec3 &prim_vec, Vec3 &sec_vec);