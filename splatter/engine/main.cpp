/**
 * @file main.cpp
 * @brief Main entry point for the Splatter Engine IPC server.
 *
 * This program implements a minimal IPC server that communicates with a Python client
 * using JSON messages over stdin/stdout. It leverages Boost.Interprocess for efficient
 * handling of large data arrays via shared memory segments to avoid copying overhead.
 *
 * @section Protocol
 * The communication protocol uses JSON for control messages and shared memory for data:
 * - **Request Format**: {"id": N, "op": "prepare", "shm_verts": "segment_name", ...}
 *   - id: Unique request identifier
 *   - op: Operation type (currently only "prepare" is supported)
 *   - shm_*: Shared memory segment names for vertices, edges, rotations, scales, offsets
 *   - *_counts: Arrays specifying counts for vertices, edges, and objects per batch
 * - **Response Format**: {"id": N, "ok": true, "rots": [...], "trans": [...]} or error
 * - **Shared Memory**: Python creates read-write segments; engine maps them read-write for processing
 *
 * @section Dependencies
 * - Boost.Interprocess for shared memory management
 * - Standard C++ libraries for JSON parsing and utilities
 * - Custom engine.h for core processing logic
 *
 * @author [Your Name or Team]
 * @date [Date]
 */

#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <cstdint>
#include <optional>
#include <csignal>
#include <cstdlib>
#include <span>

#include "engine.h"

#include <boost/interprocess/managed_shared_memory.hpp>
#include <boost/interprocess/shared_memory_object.hpp>
#include <boost/interprocess/mapped_region.hpp>
#include <numeric> // for std::accumulate

// Helper functions for JSON control

/**
 * @brief Splits a JSON object string into top-level fields, handling nested structures.
 * @param obj The JSON object string.
 * @return Vector of field strings.
 */
static std::vector<std::string> split_top_level_fields(const std::string &obj)
{
    std::vector<std::string> fields;
    int depth = 0;
    bool in_str = false;
    std::string cur;
    bool escape_next = false;
    bool started = false;
    for (char c : obj)
    {
        if (!started)
        {
            if (c == '{')
                started = true;
            continue;
        }
        if (in_str)
        {
            cur.push_back(c);
            if (escape_next)
            {
                escape_next = false;
                continue;
            }
            if (c == '\\')
            {
                escape_next = true;
                continue;
            }
            if (c == '"')
                in_str = false;
            continue;
        }
        switch (c)
        {
        case '"':
            in_str = true;
            cur.push_back(c);
            break;
        case '{':
        case '[':
            depth++;
            cur.push_back(c);
            break;
        case '}':
        case ']':
            depth--;
            cur.push_back(c);
            break;
        case ',':
            if (depth == 0)
            {
                fields.push_back(cur);
                cur.clear();
            }
            else
                cur.push_back(c);
            break;
        default:
            cur.push_back(c);
            break;
        }
    }
    if (!cur.empty())
        fields.push_back(cur);
    return fields;
}

/**
 * @brief Extracts the value for a given key from a JSON object string.
 * @param line The JSON string.
 * @param key The key to find.
 * @return Optional string value if found.
 */
static std::optional<std::string> get_value(const std::string &line, const std::string &key)
{
    auto fields = split_top_level_fields(line);
    std::string pat = "\"" + key + "\":";
    for (auto &f : fields)
    {
        auto pos = f.find(pat);
        if (pos != std::string::npos)
        {
            auto val = f.substr(pos + pat.size());
            auto start = val.find_first_not_of(" \t\r\n");
            if (start == std::string::npos)
                return std::string();
            auto end = val.find_last_not_of(" \t\r\n");
            return val.substr(start, end - start + 1);
        }
    }
    return std::nullopt;
}

/**
 * @brief Parses a JSON array string into a vector of uint32_t.
 * @param jsonArr The JSON array string.
 * @param out The output vector.
 * @return True if parsing succeeded.
 */
static bool parse_uint_array(const std::string &jsonArr, std::vector<uint32_t> &out)
{
    if (jsonArr.empty())
        return false;
    size_t i = 0;
    while (i < jsonArr.size() && (jsonArr[i] == ' ' || jsonArr[i] == '\t'))
        ++i;
    if (i == jsonArr.size() || jsonArr[i] != '[')
        return false;
    ++i;
    std::string num;
    bool in_num = false;
    for (; i < jsonArr.size(); ++i)
    {
        char c = jsonArr[i];
        if ((c >= '0' && c <= '9'))
        {
            num.push_back(c);
            in_num = true;
        }
        else if (c == ',' || c == ']')
        {
            if (in_num)
            {
                unsigned long v = std::stoul(num);
                if (v > std::numeric_limits<uint32_t>::max())
                    return false;
                out.push_back(static_cast<uint32_t>(v));
                num.clear();
                in_num = false;
            }
            if (c == ']')
                break;
        }
        else if (c == ' ' || c == '\t')
        {
            // skip
        }
        else
            return false;
    }
    return true;
}

/**
 * @brief Sends an error response to stdout.
 * @param id Request ID.
 * @param msg Error message.
 */
static void respond_error(int id, const std::string &msg)
{
    std::cout << '{' << "\"id\":" << id << ",\"ok\":false,\"error\":\"" << msg << "\"}" << std::endl;
}

/**
 * @brief Maps a shared memory segment for read-write access.
 * @param shm_name Name of the shared memory segment.
 * @param expected_size Expected size in bytes.
 * @param type_name Descriptive name for error messages.
 * @return Pointer to the mapped memory.
 * @throws std::runtime_error if size mismatch.
 */
inline boost::interprocess::mapped_region map_shared_memory(const std::string &shm_name, uint32_t expected_size, const std::string &type_name)
{
    // Note: We must keep the mapped_region alive while using the pointer it returns.
    // Returning the mapped_region by value (move) ensures the mapping stays valid
    // for the caller's scope.
    boost::interprocess::shared_memory_object obj(
        boost::interprocess::open_only, shm_name.c_str(), boost::interprocess::read_write);
    boost::interprocess::mapped_region region(obj, boost::interprocess::read_write);
    if (region.get_size() < expected_size)
    {
        throw std::runtime_error(type_name + " shared memory size mismatch");
    }
    return region; // moved to caller
}

/**
 * @brief Handles the "prepare" operation by parsing input, mapping shared memory, and processing objects.
 * @param id Request ID for response correlation.
 * @param line The JSON input line containing the request.
 */
void handle_prepare(int id, const std::string &line)
{
    std::string shm_verts, shm_edges, shm_rotations, shm_scales, shm_offsets;
    std::vector<uint32_t> vertCounts, edgeCounts, objectCounts;

    // Parse required string fields
    std::vector<std::pair<std::string, std::string *>> stringFields = {
        {"shm_verts", &shm_verts},
        {"shm_edges", &shm_edges},
        {"shm_rotations", &shm_rotations},
        {"shm_scales", &shm_scales},
        {"shm_offsets", &shm_offsets}};
    for (auto &[key, ptr] : stringFields)
    {
        if (auto v = get_value(line, key))
        {
            std::string val = *v;
            if (!val.empty() && val.front() == '"' && val.back() == '"')
                val = val.substr(1, val.size() - 2);
            *ptr = val;
        }
        else
        {
            respond_error(id, "missing " + key);
            return;
        }
    }

    // Parse required array fields
    std::vector<std::pair<std::string, std::vector<uint32_t> *>> arrayFields = {
        {"vert_counts", &vertCounts},
        {"edge_counts", &edgeCounts},
        {"object_counts", &objectCounts}};
    for (auto &[key, ptr] : arrayFields)
    {
        if (auto v = get_value(line, key))
        {
            if (!parse_uint_array(*v, *ptr))
            {
                respond_error(id, "invalid " + key);
                return;
            }
        }
        else
        {
            respond_error(id, "missing " + key);
            return;
        }
    }

    uint32_t num_objects = static_cast<uint32_t>(vertCounts.size());
    if (num_objects == 0)
    {
        std::cout << '{' << "\"id\":" << id << ",\"ok\":true,\"rots\":[],\"trans\":[]}" << std::endl;
        return;
    }
    if (edgeCounts.size() != num_objects)
    {
        respond_error(id, "edge_counts size mismatch");
        return;
    }

    // Calculate totals and expected sizes
    uint32_t total_verts = std::accumulate(vertCounts.begin(), vertCounts.end(), 0U);
    uint32_t total_edges = std::accumulate(edgeCounts.begin(), edgeCounts.end(), 0U);
    uint32_t expected_verts_size = total_verts * sizeof(Vec3);
    uint32_t expected_edges_size = total_edges * sizeof(uVec2i);
    uint32_t expected_rotations_size = num_objects * sizeof(Quaternion);
    uint32_t expected_scales_size = num_objects * sizeof(Vec3);
    uint32_t expected_offsets_size = num_objects * sizeof(Vec3);

    // Map shared memory segments and keep regions alive in this scope
    auto verts_region = map_shared_memory(shm_verts, expected_verts_size, "verts");
    auto edges_region = map_shared_memory(shm_edges, expected_edges_size, "edges");
    auto rotations_region = map_shared_memory(shm_rotations, expected_rotations_size, "rotations");
    auto scales_region = map_shared_memory(shm_scales, expected_scales_size, "scales");
    auto offsets_region = map_shared_memory(shm_offsets, expected_offsets_size, "offsets");

    std::span<Vec3> verts(static_cast<Vec3 *>(verts_region.get_address()), total_verts);
    std::span<uVec2i> edges(static_cast<uVec2i *>(edges_region.get_address()), total_edges);
    std::span<Quaternion> rotations(static_cast<Quaternion *>(rotations_region.get_address()), num_objects);
    std::span<Vec3> scales(static_cast<Vec3 *>(scales_region.get_address()), num_objects);
    std::span<Vec3> offsets(static_cast<Vec3 *>(offsets_region.get_address()), num_objects);

    // Prepare output vectors
    std::vector<Quaternion> outR(num_objects);
    std::vector<Vec3> outT(num_objects);

    // Process the batch
    // group_objects();
    prepare_object_batch(verts, edges, vertCounts, edgeCounts, outR, outT);

    // Build JSON response
    std::ostringstream rotsJson, transJson;
    rotsJson << '[';
    for (size_t i = 0; i < outR.size(); ++i)
    {
        if (i)
            rotsJson << ',';
        rotsJson << '[' << outR[i].w << ',' << outR[i].x << ',' << outR[i].y << ',' << outR[i].z << ']';
    }
    rotsJson << ']';
    transJson << '[';
    for (size_t i = 0; i < outT.size(); ++i)
    {
        if (i)
            transJson << ',';
        transJson << '[' << outT[i].x << ',' << outT[i].y << ',' << outT[i].z << ']';
    }
    transJson << ']';
    //Print to cerr for debugging:
    std::cerr << '{' << "\"id\":" << id << ",\"ok\":true,\"rots\":" << rotsJson.str() << ",\"trans\":" << transJson.str() << '}' << std::endl;
    std::cout << '{' << "\"id\":" << id << ",\"ok\":true,\"rots\":" << rotsJson.str() << ",\"trans\":" << transJson.str() << '}' << std::endl;
}

/**
 * @brief Main entry point: runs the IPC server loop.
 * Reads JSON requests from stdin, processes them, and writes responses to stdout.
 */

/**
 * @brief Signal handler for crashes.
 */
void signal_handler(int signal) {
    std::cerr << "[engine] Received signal " << signal << ": ";
    if (signal == SIGSEGV) {
        std::cerr << "Segmentation fault" << std::endl;
    } else if (signal == SIGABRT) {
        std::cerr << "Aborted" << std::endl;
    } else if (signal == SIGFPE) {
        std::cerr << "Floating point exception" << std::endl;
    } else {
        std::cerr << "Unknown signal" << std::endl;
    }
    std::exit(1);
}

int main(int argc, char **argv)
{
    std::cerr << "[engine] IPC server starting" << std::endl;

    // Install signal handlers for common crashes
    std::signal(SIGSEGV, signal_handler);
    std::signal(SIGABRT, signal_handler);
    std::signal(SIGFPE, signal_handler);

    std::string line;
    while (std::getline(std::cin, line))
    {
        if (line.empty())
            continue; // Skip empty lines
        if (line == "__quit__")
            break; // Exit on quit signal
        // Parse request ID and operation
        auto idVal = get_value(line, "id");
        int id = idVal ? std::stoi(*idVal) : -1;
        auto opVal = get_value(line, "op");
        if (!opVal)
        {
            respond_error(id, "missing op");
            continue;
        }
        std::string op = *opVal;
        if (!op.empty() && op.front() == '"' && op.back() == '"')
            op = op.substr(1, op.size() - 2); // Remove quotes

        try
        {
            if (op == "prepare")
            {
                handle_prepare(id, line);
            }
            else
            {
                respond_error(id, "unknown op");
            }
        }
        catch (const std::exception &e)
        {
            respond_error(id, e.what());
        }
    }
    std::cerr << "[engine] IPC server exiting" << std::endl;
    return 0;
}