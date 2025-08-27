#pragma once
#include <cstdint>
#include <cmath>
#include <type_traits>

// Primary template flag
template<typename T>
inline constexpr bool TVecIsFloat = std::is_floating_point_v<T>;

// ---------------- 2D ----------------
template<typename T, bool IsFloat = TVecIsFloat<T>>
struct TVec2 {
    T x{}, y{};
    constexpr TVec2() = default;
    constexpr TVec2(T x_val, T y_val) : x(x_val), y(y_val) {}
    constexpr bool operator<(const TVec2& o) const {
        return x < o.x || (x == o.x && y < o.y);
    }
    constexpr TVec2 operator-(const TVec2& o) const { return {T(x - o.x), T(y - o.y)}; }
    constexpr TVec2 operator+(const TVec2& o) const { return {T(x + o.x), T(y + o.y)}; }
    constexpr TVec2 operator*(T s) const { return {T(x * s), T(y * s)}; }
    // dot/cross kept for all types (remove if you want them float-only)
    constexpr auto dot(const TVec2& o) const { return x * o.x + y * o.y; }
    constexpr auto cross(const TVec2& o) const { return x * o.y - y * o.x; }
};

// Floating-point 2D specialization adds length utilities
template<typename T>
struct TVec2<T, true> {
    T x{}, y{};
    constexpr TVec2() = default;
    constexpr TVec2(T x_val, T y_val) : x(x_val), y(y_val) {}
    constexpr bool operator<(const TVec2& o) const {
        return x < o.x || (x == o.x && y < o.y);
    }
    constexpr TVec2 operator-(const TVec2& o) const { return {T(x - o.x), T(y - o.y)}; }
    constexpr TVec2 operator+(const TVec2& o) const { return {T(x + o.x), T(y + o.y)}; }
    constexpr TVec2 operator*(T s) const { return {T(x * s), T(y * s)}; }
    constexpr T dot(const TVec2& o) const { return x * o.x + y * o.y; }
    constexpr T cross(const TVec2& o) const { return x * o.y - y * o.x; }
    constexpr T length_squared() const { return x * x + y * y; }
    T length() const { return std::sqrt(length_squared()); }
    TVec2 normalized() const {
        T len = length();
        return (len > T(0)) ? TVec2{x / len, y / len} : TVec2{};
    }
};

// ---------------- 3D ----------------
template<typename T, bool IsFloat = TVecIsFloat<T>>
struct TVec3 {
    T x{}, y{}, z{};
    constexpr TVec3() = default;
    constexpr TVec3(T x_val, T y_val, T z_val) : x(x_val), y(y_val), z(z_val) {}
    constexpr TVec3(const TVec2<T>& v2, T z_val = T{}) : x(v2.x), y(v2.y), z(z_val) {}
    constexpr bool operator<(const TVec3& o) const {
        return x < o.x || (x == o.x && (y < o.y || (y == o.y && z < o.z)));
    }
    constexpr bool operator==(const TVec3& o) const { return x == o.x && y == o.y && z == o.z; }
    constexpr TVec3 operator-(const TVec3& o) const { return {T(x - o.x), T(y - o.y), T(z - o.z)}; }
    constexpr TVec3 operator+(const TVec3& o) const { return {T(x + o.x), T(y + o.y), T(z + o.z)}; }
    TVec3 operator/(uint32_t s) const { return {T(x / s), T(y / s), T(z / s)}; }
    constexpr TVec3 operator*(float s) const { return {T(x * s), T(y * s), T(z * s)}; }
    constexpr auto dot(const TVec3& o) const { return x * o.x + y * o.y + z * o.z; }
    constexpr TVec3 cross(const TVec3& o) const {
        return TVec3{
            T(y * o.z - z * o.y),
            T(z * o.x - x * o.z),
            T(x * o.y - y * o.x)
        };
    }
};

// Floating-point 3D specialization adds length utilities
template<typename T>
struct TVec3<T, true> {
    T x{}, y{}, z{};
    constexpr TVec3() = default;
    constexpr TVec3(T x_val, T y_val, T z_val) : x(x_val), y(y_val), z(z_val) {}
    constexpr TVec3(const TVec2<T>& v2, T z_val = T{}) : x(v2.x), y(v2.y), z(z_val) {}
    constexpr bool operator<(const TVec3& o) const {
        return x < o.x || (x == o.x && (y < o.y || (y == o.y && z < o.z)));
    }
    constexpr bool operator==(const TVec3& o) const { return x == o.x && y == o.y && z == o.z; }
    constexpr TVec3 operator-(const TVec3& o) const { return {T(x - o.x), T(y - o.y), T(z - o.z)}; }
    constexpr TVec3 operator+(const TVec3& o) const { return {T(x + o.x), T(y + o.y), T(z + o.z)}; }
    TVec3 operator/(uint32_t s) const { return {T(x / s), T(y / s), T(z / s)}; }
    constexpr TVec3 operator*(float s) const { return {T(x * s), T(y * s), T(z * s)}; }
    constexpr T dot(const TVec3& o) const { return x * o.x + y * o.y + z * o.z; }
    constexpr TVec3 cross(const TVec3& o) const {
        return TVec3{
            T(y * o.z - z * o.y),
            T(z * o.x - x * o.z),
            T(x * o.y - y * o.x)
        };
    }
    constexpr T length_squared() const { return x * x + y * y + z * z; }
    T length() const { return std::sqrt(length_squared()); }
    TVec3 normalized() const {
        T len = length();
        return (len > T(0)) ? TVec3{x / len, y / len, z / len} : TVec3{};
    }
};

using Vec2  = TVec2<float>;
using Vec3  = TVec3<float>;
using Vec2i = TVec2<int32_t>;
using uVec2i = TVec2<uint32_t>;
using Vec3i = TVec3<int32_t>;
using uVec3i = TVec3<uint32_t>;