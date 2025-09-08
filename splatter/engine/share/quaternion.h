#pragma once
#include "vec.h"

#include <cmath>

struct Quaternion {
    float w, x, y, z;

    // Default constructor (identity quaternion)
    Quaternion() : w(1.0f), x(0.0f), y(0.0f), z(0.0f) {}

    // Constructor from components
    Quaternion(float w_val, float x_val, float y_val, float z_val)
        : w(w_val), x(x_val), y(y_val), z(z_val) {}

    // Constructor from axis and angle (angle in radians)
    // Remember to normalize the axis if not already unit length!
    Quaternion(const Vec3& axis, float angle_rad) {
        float half_angle = angle_rad * 0.5f;
        float sin_half_angle = std::sin(half_angle);
        w = std::cos(half_angle);
        x = axis.x * sin_half_angle;
        y = axis.y * sin_half_angle;
        z = axis.z * sin_half_angle;
        normalize(); // Important: ensure it's a unit quaternion
    }

    // Quaternion multiplication (q1 * q2)
    // ... (as provided in earlier responses)

    // Conjugate: changes sign of x, y, z components
    Quaternion conjugate() const {
        return Quaternion(w, -x, -y, -z);
    }

    // Magnitude (length)
    float magnitude() const {
        return std::sqrt(w*w + x*x + y*y + z*z);
    }

    // Normalize: converts to a unit quaternion
    void normalize() {
        float mag = magnitude();
        if (mag > 0.0f) { // Avoid division by zero
            w /= mag;
            x /= mag;
            y /= mag;
            z /= mag;
        } else {
            // Handle zero magnitude, e.g., set to identity
            w = 1.0f; x = 0.0f; y = 0.0f; z = 0.0f;
        }
    }
};