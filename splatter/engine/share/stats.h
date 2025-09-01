#pragma once

#include <vector>
#include <cstdint>

double find_center(std::vector<uint32_t> &data);

std::vector<uint32_t> exclude_outliers_iqr(std::vector<uint32_t> data);