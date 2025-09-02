#include "linalg3.h"

#include "share/vec.h"

#include <Eigen/Dense>

#include <cstdint>
#include <vector>
#include <cmath>
#include <algorithm>

// ============================================================================
// Public API Functions
// ============================================================================

/**
 * @brief Compute covariance matrix for 3D vertices
 * @param idxs Indices of vertices to include in computation
 * @param verts Array of 3D vertices
 * @param cov Output 3x3 covariance matrix
 */
void compute_cov(const std::vector<uint32_t> &idxs, const Vec3 *verts, float cov[3][3])
{
    const size_t n = idxs.size();
    if (n == 0) {
        std::fill(&cov[0][0], &cov[0][0] + 9, 0.0f);
        return;
    }

    // Collect points into Eigen matrix
    Eigen::Matrix<float, 3, Eigen::Dynamic> data(3, n);
    for (size_t i = 0; i < n; ++i) {
        const Vec3& v = verts[idxs[i]];
        data(0, i) = v.x;
        data(1, i) = v.y;
        data(2, i) = v.z;
    }

    // Compute mean
    Eigen::Vector3f mean = data.rowwise().mean();

    // Center the data
    Eigen::Matrix<float, 3, Eigen::Dynamic> centered = data.colwise() - mean;

    // Compute covariance
    Eigen::Matrix3f cov_mat = (centered * centered.transpose()) / static_cast<float>(n);

    // Copy to output
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j)
            cov[i][j] = cov_mat(i, j);
}

/**
 * @brief Compute covariance matrix for 2D vertices
 * @param idxs Indices of vertices to include in computation
 * @param verts Array of 2D vertices
 * @param cov Output 2x2 covariance matrix
 */
void compute_cov(const std::vector<uint32_t> &idxs, const Vec2 *verts, float cov[2][2])
{
    const size_t n = idxs.size();
    if (n == 0) {
        std::fill(&cov[0][0], &cov[0][0] + 4, 0.0f);
        return;
    }

    // Collect points into Eigen matrix
    Eigen::Matrix<float, 2, Eigen::Dynamic> data(2, n);
    for (size_t i = 0; i < n; ++i) {
        const Vec2& v = verts[idxs[i]];
        data(0, i) = v.x;
        data(1, i) = v.y;
    }

    // Compute mean
    Eigen::Vector2f mean = data.rowwise().mean();

    // Center the data
    Eigen::Matrix<float, 2, Eigen::Dynamic> centered = data.colwise() - mean;

    // Compute covariance
    Eigen::Matrix2f cov_mat = (centered * centered.transpose()) / static_cast<float>(n);

    // Copy to output
    for (int i = 0; i < 2; ++i)
        for (int j = 0; j < 2; ++j)
            cov[i][j] = cov_mat(i, j);
}

/**
 * @brief Compute eigenvalues and eigenvectors of 3x3 matrix using Eigen
 * @param A Input 3x3 matrix
 * @param lambda1 Output: largest eigenvalue
 * @param lambda2 Output: middle eigenvalue
 * @param lambda3 Output: smallest eigenvalue
 * @param prim_vec Output: eigenvector for lambda1
 * @param sec_vec Output: eigenvector for lambda2
 * @param third_vec Output: eigenvector for lambda3
 */
void eig3(const float A[3][3], float &lambda1, float &lambda2, float &lambda3, Vec3 &prim_vec, Vec3 &sec_vec, Vec3 &third_vec)
{
    Eigen::Matrix3f mat;
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j)
            mat(i, j) = A[i][j];

    Eigen::SelfAdjointEigenSolver<Eigen::Matrix3f> solver(mat);
    if (solver.info() != Eigen::Success) {
        // Fallback for degenerate cases
        lambda1 = lambda2 = lambda3 = 0.0f;
        prim_vec = Vec3{1.0f, 0.0f, 0.0f};
        sec_vec = Vec3{0.0f, 1.0f, 0.0f};
        third_vec = Vec3{0.0f, 0.0f, 1.0f};
        return;
    }

    Eigen::Vector3f eigenvalues = solver.eigenvalues();
    Eigen::Matrix3f eigenvectors = solver.eigenvectors();

    // Eigen sorts eigenvalues in increasing order, so:
    // eigenvalues(0) = smallest, eigenvalues(1) = middle, eigenvalues(2) = largest
    lambda3 = eigenvalues(0);  // Smallest
    lambda2 = eigenvalues(1);  // Middle
    lambda1 = eigenvalues(2);  // Largest

    Eigen::Vector3f ev1 = eigenvectors.col(2);  // Largest eigenvalue's eigenvector
    Eigen::Vector3f ev2 = eigenvectors.col(1);  // Middle eigenvalue's eigenvector
    Eigen::Vector3f ev3 = eigenvectors.col(0);  // Smallest eigenvalue's eigenvector

    prim_vec = Vec3{ev1.x(), ev1.y(), ev1.z()};
    sec_vec = Vec3{ev2.x(), ev2.y(), ev2.z()};
    third_vec = Vec3{ev3.x(), ev3.y(), ev3.z()};
}

/**
 * @brief Compute eigenvalues and eigenvectors of 2x2 matrix using Eigen
 * @param A Input 2x2 matrix
 * @param lambda1 Output: first eigenvalue
 * @param lambda2 Output: second eigenvalue
 * @param prim_vec Output: eigenvector for lambda1
 * @param sec_vec Output: eigenvector for lambda2
 */
void eig2(const float A[2][2], float &lambda1, float &lambda2, Vec2 &prim_vec, Vec2 &sec_vec)
{
    Eigen::Matrix2f mat;
    for (int i = 0; i < 2; ++i)
        for (int j = 0; j < 2; ++j)
            mat(i, j) = A[i][j];

    Eigen::SelfAdjointEigenSolver<Eigen::Matrix2f> solver(mat);
    if (solver.info() != Eigen::Success) {
        // Fallback
        lambda1 = lambda2 = 0.0f;
        prim_vec = Vec2{1.0f, 0.0f};
        sec_vec = Vec2{0.0f, 1.0f};
        return;
    }

    Eigen::Vector2f eigenvalues = solver.eigenvalues();
    Eigen::Matrix2f eigenvectors = solver.eigenvectors();

    // Eigen sorts in increasing order
    lambda1 = eigenvalues(1);  // Largest
    lambda2 = eigenvalues(0);  // Smallest

    Eigen::Vector2f ev1 = eigenvectors.col(1);
    Eigen::Vector2f ev2 = eigenvectors.col(0);

    prim_vec = Vec2{ev1.x(), ev1.y()};
    sec_vec = Vec2{ev2.x(), ev2.y()};
}