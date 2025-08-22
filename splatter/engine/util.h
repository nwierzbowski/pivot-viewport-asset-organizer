#pragma once

#include <cmath>
#include <cstdint>

struct Vec2i {
    int32_t x = 0, y = 0;

    Vec2i() = default;
    Vec2i(int32_t x_val, int32_t y_val) : x(x_val), y(y_val) {}

    bool operator<(const Vec2i &other) const {
        return x < other.x || (x == other.x && y < other.y);
    }

    Vec2i operator-(const Vec2i& other) const {
        return {x - other.x, y - other.y};
    }
    
    Vec2i operator+(const Vec2i& other) const {
        return {x + other.x, y + other.y};
    }
    
    Vec2i operator*(int32_t scale) const {
        return {x * scale, y * scale};
    }
};


struct uVec2i {
    uint32_t x = 0, y = 0;

    uVec2i() = default;
    uVec2i(uint32_t x_val, uint32_t y_val) : x(x_val), y(y_val) {}

    bool operator<(const uVec2i &other) const {
        return x < other.x || (x == other.x && y < other.y);
    }

    uVec2i operator-(const uVec2i& other) const {
        return {x - other.x, y - other.y};
    }

    uVec2i operator+(const uVec2i& other) const {
        return {x + other.x, y + other.y};
    }

    uVec2i operator*(uint32_t scale) const {
        return {x * scale, y * scale};
    }
};

struct Vec3i {
    int32_t x = 0, y = 0, z = 0;

    Vec3i() = default;
    Vec3i(int32_t x_val, int32_t y_val, int32_t z_val) : x(x_val), y(y_val), z(z_val) {}

    bool operator<(const Vec3i &other) const {
        return x < other.x || (x == other.x && y < other.y) || (x == other.x && y == other.y && z < other.z);
    }

    Vec3i operator-(const Vec3i& other) const {
        return {x - other.x, y - other.y, z - other.z};
    }

    Vec3i operator+(const Vec3i& other) const {
        return {x + other.x, y + other.y, z + other.z};
    }

    Vec3i operator*(int32_t scale) const {
        return {x * scale, y * scale, z * scale};
    }
};

struct uVec3i {
    uint32_t x = 0, y = 0, z = 0;

    uVec3i() = default;
    uVec3i(uint32_t x_val, uint32_t y_val, uint32_t z_val) : x(x_val), y(y_val), z(z_val) {}

    bool operator<(const uVec3i &other) const {
        return x < other.x || (x == other.x && y < other.y) || (x == other.x && y == other.y && z < other.z);
    }

    uVec3i operator-(const uVec3i& other) const {
        return {x - other.x, y - other.y, z - other.z};
    }

    uVec3i operator+(const uVec3i& other) const {
        return {x + other.x, y + other.y, z + other.z};
    }

    uVec3i operator*(uint32_t scale) const {
        return {x * scale, y * scale, z * scale};
    }
};

struct Vec2 { 
    float x = 0.0f, y = 0.0f;

    Vec2() = default;
    Vec2(float x_val, float y_val) : x(x_val), y(y_val) {}

    bool operator<(const Vec2 &other) const {
        return x < other.x || (x == other.x && y < other.y);
    }

    Vec2 operator-(const Vec2& other) const {
    return {x - other.x, y - other.y};
    }
    
    Vec2 operator+(const Vec2& other) const {
        return {x + other.x, y + other.y};
    }
    
    Vec2 operator*(float scale) const {
        return {x * scale, y * scale};
    }
    
    float dot(const Vec2& other) const {
        return x * other.x + y * other.y;
    }
    
    float cross(const Vec2& other) const {
        return x * other.y - y * other.x;
    }
    
    float length_squared() const {
        return x * x + y * y;
    }
    
    float length() const {
        return std::sqrt(length_squared());
    }
    
    Vec2 normalized() const {
        float len = length();
        return len > 0 ? Vec2{x / len, y / len} : Vec2{0, 0};
    }
};

struct Vec3 {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;

    Vec3() = default;
    Vec3(float x_val, float y_val, float z_val) : x(x_val), y(y_val), z(z_val) {}
    Vec3(const Vec2& v2, float z_val = 0.0f) : x(v2.x), y(v2.y), z(z_val) {}

    bool operator<(const Vec3 &other) const {
        return x < other.x || (x == other.x && y < other.y) || (x == other.x && y == other.y && z < other.z);
    }

    Vec3 operator-(const Vec3& other) const {
    return {x - other.x, y - other.y, z - other.z};
    }

    Vec3 operator+(const Vec3& other) const {
        return {x + other.x, y + other.y, z + other.z};
    }
    
    Vec3 operator*(float scale) const {
        return {x * scale, y * scale, z * scale};
    }
    
    float dot(const Vec3& other) const {
        return x * other.x + y * other.y + z * other.z;
    }
    
    Vec3 cross(const Vec3& other) const {
        return Vec3{
            y * other.z - z * other.y,
            z * other.x - x * other.z,
            x * other.y - y * other.x
        };
    }
    
    float length_squared() const {
        return x * x + y * y + z * z;
    }
    
    float length() const {
        return std::sqrt(length_squared());
    }
    
    Vec3 normalized() const {
        float len = length();
        return len > 0 ? Vec3{x / len, y / len, z / len} : Vec3{0, 0, 0};
    }
};

struct BoundingBox2D {
    Vec2 min_corner;
    Vec2 max_corner;
    float area;
    float rotation_angle;  // Radians

    BoundingBox2D() : area(std::numeric_limits<float>::max()), rotation_angle(0) {}
};