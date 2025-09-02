#include "voxel.h"

#include "share/vec.h"
#include "object/util/linalg3.h"

#include <vector>
#include <unordered_map>

VoxelMap build_voxel_map(const Vec3 *verts, const Vec3 *norms, uint32_t vertCount, float voxelSize)
{
    VoxelMap voxel_map;
    if (!verts || vertCount == 0)
        return voxel_map;

    voxel_map.reserve(vertCount / 4 + 1);

    for (uint32_t i = 0; i < vertCount; ++i)
    {
        VoxelKey key = make_voxel_key(verts[i], voxelSize);
        voxel_map[key].vertex_indices.push_back(i);
    }
    

    for (auto &[voxel_coord, voxel_data] : voxel_map)
    {
        const size_t cnt = voxel_data.vertex_indices.size();

        Vec3 avg_normal{0, 0, 0};
        for (uint32_t i : voxel_data.vertex_indices)
            avg_normal = avg_normal + norms[i];
        avg_normal = avg_normal / static_cast<float>(cnt);

        float lambda1 = 0.f, lambda2 = 0.f, lambda3 = 0.f;
        Vec3 prim_vec{0, 0, 0}, sec_vec{0, 0, 0}, third_vec{0, 0, 0};

        if (cnt >= 3)
        {
            float cov[3][3];
            compute_cov(voxel_data.vertex_indices, verts, cov);
            eig3(cov, lambda1, lambda2, lambda3, prim_vec, sec_vec, third_vec);
        }

        voxel_data.avg_normal = avg_normal;
        voxel_data.prim_vec = prim_vec;
        voxel_data.sec_vec = sec_vec;
        voxel_data.third_vec = third_vec;
        voxel_data.lambda1 = lambda1;
        voxel_data.lambda2 = lambda2;
        voxel_data.lambda3 = lambda3;
    }

    return voxel_map;
}