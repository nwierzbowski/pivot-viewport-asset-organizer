#include "voxel.h"

#include "share/vec.h"
#include "object/util/linalg3.h"

#include <vector>
#include <unordered_map>
#include <span>

VoxelMap build_voxel_map(std::span<const Vec3> verts, float voxelSize)
{
    VoxelMap voxel_map;
    if (verts.empty())
        return voxel_map;

    voxel_map.reserve(verts.size() / 4 + 1);

    for (size_t i = 0; i < verts.size(); ++i)
    {
        VoxelKey key = make_voxel_key(verts[i], voxelSize);
        voxel_map[key].vertex_indices.push_back(static_cast<uint32_t>(i));
        voxel_map[key].centroid += verts[i];
    }

    for (auto &[voxel_coord, voxel_data] : voxel_map)
    {
        const size_t count = voxel_data.vertex_indices.size();

        voxel_data.centroid /= static_cast<float>(count);

        float lambda1 = 0.f, lambda2 = 0.f, lambda3 = 0.f;
        Vec3 prim_vec{0, 0, 0}, sec_vec{0, 0, 0}, third_vec{0, 0, 0};

        float proj_lambda1 = 0.0f, proj_lambda2 = 0.0f;
        Vec2 proj_prim_vec{0, 0}, proj_sec_vec{0, 0};

        if (count >= 6)
        {
            float cov[3][3];
            compute_cov(voxel_data.vertex_indices, verts.data(), cov);
            eig3(cov, lambda1, lambda2, lambda3, prim_vec, sec_vec, third_vec);

            // Only compute projections and 2D eigenvalues if we have a valid basis
            std::vector<Vec2> proj_norms;
            proj_norms.reserve(count);
            for (uint32_t i : voxel_data.vertex_indices)
            {
                Vec3 rel_vec = (verts[i] - voxel_data.centroid);
                Vec2 proj = project_to_basis_coeffs(sec_vec, third_vec, rel_vec);
                proj_norms.emplace_back(proj);
            }

            float proj_cov[2][2];
            compute_cov(proj_norms, proj_cov);

            eig2(proj_cov, proj_lambda1, proj_lambda2, proj_prim_vec, proj_sec_vec);
        }

        voxel_data.prim_vec = prim_vec;
        voxel_data.sec_vec = sec_vec;
        voxel_data.third_vec = third_vec;
        voxel_data.lambda1 = lambda1;
        voxel_data.lambda2 = lambda2;
        voxel_data.lambda3 = lambda3;

        voxel_data.projected_lambda1 = proj_lambda1;
        voxel_data.projected_lambda2 = proj_lambda2;
        voxel_data.projected_prim_vec = proj_prim_vec;
        voxel_data.projected_sec_vec = proj_sec_vec;
    }

    // ... (return statement remains the same)

    return voxel_map;
}