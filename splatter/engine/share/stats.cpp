#include "stats.h"

#include <vector>
#include <cstdint>
#include <algorithm>

// Function to find the center of a vector
double find_center(std::vector<uint32_t> &data)
{
    size_t n = data.size();
    if (n % 2 == 1)
    {
        return static_cast<double>(data[n / 2]);
    }
    else
    {
        return (static_cast<double>(data[n / 2 - 1]) + data[n / 2]) / 2.0;
    }
}

// Function to exclude outliers using the IQR method
std::vector<uint32_t> exclude_outliers_iqr(std::vector<uint32_t> data)
{
    // Sort the data to find quartiles
    std::sort(data.begin(), data.end());

    size_t n = data.size();
    if (n < 4)
        return data; // Not enough data to reliably find quartiles

    // Find Q1 and Q3
    std::vector<uint32_t> lower_half(data.begin(), data.begin() + n / 2);
    std::vector<uint32_t> upper_half(data.begin() + (n + 1) / 2, data.end());

    double q1 = find_center(lower_half);
    double q3 = find_center(upper_half);

    double iqr = q3 - q1;
    double lower_bound = q1 - 1.5 * iqr;
    double upper_bound = q3 + 1.5 * iqr;

    // Use a temporary vector to store the non-outliers
    std::vector<uint32_t> filtered_data;
    for (uint32_t val : data)
    {
        if (val >= lower_bound && val <= upper_bound)
        {
            filtered_data.push_back(val);
        }
    }
    return filtered_data;
}