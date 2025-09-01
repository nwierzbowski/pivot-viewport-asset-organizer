#pragma once

#include <concepts>

template <typename V>
concept HasXY = requires(V v) {
    { v.x } -> std::convertible_to<float>;
    { v.y } -> std::convertible_to<float>;
};