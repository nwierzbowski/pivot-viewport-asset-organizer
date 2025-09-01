#include "object/util/linalg3.h"

#include "share/vec.h"

#include <vector>
#include <cstdint>

void compute_cov(const std::vector<uint32_t> &idxs, const Vec3 *verts, float cov[3][3])
{
    const size_t n = idxs.size();
    if (n == 0)
    {
        cov[0][0] = cov[1][1] = cov[2][2] = 0.f;
        cov[0][1] = cov[0][2] = cov[1][0] = cov[1][2] = cov[2][0] = cov[2][1] = 0.f;
        return;
    }
    float mean[3] = {0.f, 0.f, 0.f};
    for (uint32_t id : idxs)
    {
        const Vec3 &p = verts[id];
        mean[0] += p.x;
        mean[1] += p.y;
        mean[2] += p.z;
    }
    const float inv_n = 1.0f / static_cast<float>(n);
    mean[0] *= inv_n;
    mean[1] *= inv_n;
    mean[2] *= inv_n;

    // Zero
    cov[0][0] = cov[0][1] = cov[0][2] = 0.f;
    cov[1][0] = cov[1][1] = cov[1][2] = 0.f;
    cov[2][0] = cov[2][1] = cov[2][2] = 0.f;

    for (uint32_t id : idxs)
    {
        const Vec3 &p = verts[id];
        float d0 = p.x - mean[0];
        float d1 = p.y - mean[1];
        float d2 = p.z - mean[2];
        cov[0][0] += d0 * d0;
        cov[0][1] += d0 * d1;
        cov[0][2] += d0 * d2;
        cov[1][1] += d1 * d1;
        cov[1][2] += d1 * d2;
        cov[2][2] += d2 * d2;
    }
    cov[1][0] = cov[0][1];
    cov[2][0] = cov[0][2];
    cov[2][1] = cov[1][2];
    // Scale
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            cov[r][c] *= inv_n;
};

void eig3(const float A[3][3], float &lambda1, float &lambda2, Vec3 &prim_vec, Vec3 &sec_vec)
{
    // Fast power-iteration for largest eigenvalue + deflation for second.
    // Fall back to Eigen if something goes wrong.
    auto dot3 = [](const float a[3], const float b[3])
    {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    };
    auto mat_vec = [&](const float M[3][3], const float v[3], float out[3])
    {
        for (int r = 0; r < 3; ++r)
            out[r] = M[r][0] * v[0] + M[r][1] * v[1] + M[r][2] * v[2];
    };

    float M[3][3];
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            M[r][c] = A[r][c];

    const int MAX_IT = 40;
    const float TOL = 1e-10f;

    // First eigenpair
    float v[3] = {1.0f, 1.0f, 1.0f};
    float tmp[3];
    float nrm = std::sqrt(dot3(v, v));
    if (nrm == 0.0f)
    {
        v[0] = 1;
        v[1] = 0;
        v[2] = 0;
        nrm = 1.0f;
    }
    v[0] /= nrm;
    v[1] /= nrm;
    v[2] /= nrm;
    float lambda_prev = 0.0f;
    for (int it = 0; it < MAX_IT; ++it)
    {
        mat_vec(M, v, tmp);
        float tmpn = std::sqrt(dot3(tmp, tmp));
        if (tmpn == 0.0f)
            break;
        v[0] = tmp[0] / tmpn;
        v[1] = tmp[1] / tmpn;
        v[2] = tmp[2] / tmpn;
        mat_vec(M, v, tmp);
        float lambda = dot3(v, tmp);
        if (std::abs(lambda - lambda_prev) < TOL * std::max(1.0f, std::abs(lambda)))
        {
            lambda_prev = lambda;
            break;
        }
        lambda_prev = lambda;
    }

    lambda1 = lambda_prev;
    prim_vec = Vec3{v[0], v[1], v[2]};

    // Deflate and find second eigenvector (use original M to compute Rayleigh quotient)
    float M2[3][3];
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            M2[r][c] = M[r][c] - lambda1 * v[r] * v[c];

    float u[3] = {v[1] - v[2] + 1e-1f, v[2] - v[0] + 1e-1f, v[0] - v[1] + 1e-1f};
    nrm = std::sqrt(dot3(u, u));
    if (nrm == 0.0f)
    {
        u[0] = 1;
        u[1] = 0;
        u[2] = 0;
        nrm = 1.0f;
    }
    u[0] /= nrm;
    u[1] /= nrm;
    u[2] /= nrm;
    float lambda2_prev = 0.0f;
    for (int it = 0; it < MAX_IT; ++it)
    {
        mat_vec(M2, u, tmp);
        float tmpn = std::sqrt(dot3(tmp, tmp));
        if (tmpn == 0.0f)
            break;
        u[0] = tmp[0] / tmpn;
        u[1] = tmp[1] / tmpn;
        u[2] = tmp[2] / tmpn;
        mat_vec(M, u, tmp); // original matrix for Rayleigh
        float lambda = dot3(u, tmp);
        if (std::abs(lambda - lambda2_prev) < TOL * std::max(1.0f, std::abs(lambda)))
        {
            lambda2_prev = lambda;
            break;
        }
        lambda2_prev = lambda;
    }
    lambda2 = lambda2_prev;
    sec_vec = Vec3{u[0], u[1], u[2]};
};