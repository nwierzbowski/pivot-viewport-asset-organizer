#pragma once

#include "share/vec.h"

#include <vector>
#include <cstdint>

void compute_cov(const std::vector<uint32_t> &idxs, const Vec3 *verts, float cov[3][3]);

void compute_cov(const std::vector<uint32_t> &idxs, const Vec2 *verts, float cov[2][2]);

void eig3(const float A[3][3], float &lambda1, float &lambda2, float &lambda3, Vec3 &prim_vec, Vec3 &sec_vec, Vec3 &third_vec);

void eig2(const float A[2][2], float &lambda1, float &lambda2, Vec2 &prim_vec, Vec2 &sec_vec);