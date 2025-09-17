// Minimal JSON-over-stdin/stdout IPC loop with Boost.Interprocess shared memory for large data.
// Protocol: JSON control messages; large arrays via shared memory segments.
// Request: {"id":N, "op":"prepare", "shm_verts":"segment_name", "shm_edges":"segment_name", "shm_rotations":"segment_name", "shm_scales":"segment_name", "shm_offsets":"segment_name", "vert_counts":[...], "edge_counts":[...], "object_counts":[...]}
// Response: {"id":N, "ok":true, "rots":[...], "trans":[...]} or error.
// Shared memory: Python creates segments, engine maps them read-only, processes in-place.

#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <cstdint>
#include <optional>

#include "engine.h"

#include <boost/interprocess/managed_shared_memory.hpp>
#include <boost/interprocess/shared_memory_object.hpp>
#include <boost/interprocess/mapped_region.hpp>
#include <numeric> // for std::accumulate

// Helper functions for JSON control
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

static void respond_error(int id, const std::string &msg)
{
    std::cout << '{' << "\"id\":" << id << ",\"ok\":false,\"error\":\"" << msg << "\"}" << std::endl;
}

inline void *map_shared_memory(const std::string &shm_name, uint32_t expected_size, const std::string &type_name)
{
    boost::interprocess::shared_memory_object obj(boost::interprocess::open_only, shm_name.c_str(), boost::interprocess::read_only);
    boost::interprocess::mapped_region region(obj, boost::interprocess::read_only);
    if (region.get_size() < expected_size)
    {
        throw std::runtime_error(type_name + " shared memory size mismatch");
    }
    return region.get_address();
}

int main(int argc, char **argv)
{
    std::cerr << "[engine] IPC server starting" << std::endl;
    std::string line;
    while (std::getline(std::cin, line))
    {
        if (line.empty())
            continue;
        if (line == "__quit__")
            break;
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
            op = op.substr(1, op.size() - 2);

        try
        {
            if (op == "prepare")
            {
                std::string shm_verts, shm_edges, shm_rotations, shm_scales, shm_offsets;
                std::vector<uint32_t> vertCounts, edgeCounts, objectCounts;

                bool parsed = true;

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
                        *ptr = *v;
                    }
                    else
                    {
                        respond_error(id, "missing " + key);
                        parsed = false;
                        break;
                    }
                }

                if (!parsed)
                    continue;

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
                            parsed = false;
                            break;
                        }
                    }
                    else
                    {
                        respond_error(id, "missing " + key);
                        parsed = false;
                        break;
                    }
                }

                if (!parsed)
                    continue;
                uint32_t num_objects = static_cast<uint32_t>(vertCounts.size());
                if (num_objects == 0)
                {
                    std::cout << '{' << "\"id\":" << id << ",\"ok\":true,\"rots\":[],\"trans\":[]}" << std::endl;
                    continue;
                }
                if (edgeCounts.size() != num_objects)
                {
                    respond_error(id, "edge_counts size mismatch");
                    continue;
                }

                uint32_t total_verts = std::accumulate(vertCounts.begin(), vertCounts.end(), 0U);
                uint32_t total_edges = std::accumulate(edgeCounts.begin(), edgeCounts.end(), 0U);
                uint32_t expected_verts_size = total_verts * sizeof(Vec3);
                uint32_t expected_edges_size = total_edges * sizeof(uVec2i);
                uint32_t expected_rotations_size = num_objects * sizeof(Quaternion);
                uint32_t expected_scales_size = num_objects * sizeof(Vec3);
                uint32_t expected_offsets_size = num_objects * sizeof(Vec3);

                const Vec3 *verts_ptr = static_cast<const Vec3 *>(map_shared_memory(shm_verts, expected_verts_size, "verts"));
                const uVec2i *edges_ptr = static_cast<const uVec2i *>(map_shared_memory(shm_edges, expected_edges_size, "edges"));
                const Quaternion *rotations_ptr = static_cast<const Quaternion *>(map_shared_memory(shm_rotations, expected_rotations_size, "rotations"));
                const Vec3 *scales_ptr = static_cast<const Vec3 *>(map_shared_memory(shm_scales, expected_scales_size, "scales"));
                const Vec3 *offsets_ptr = static_cast<const Vec3 *>(map_shared_memory(shm_offsets, expected_offsets_size, "offsets"));

                std::vector<Quaternion> outR(num_objects);
                std::vector<Vec3> outT(num_objects);
                prepare_object_batch(verts_ptr, edges_ptr, vertCounts.data(), edgeCounts.data(), num_objects, outR.data(), outT.data());
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
                std::cout << '{' << "\"id\":" << id << ",\"ok\":true,\"rots\":" << rotsJson.str() << ",\"trans\":" << transJson.str() << '}' << std::endl;
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