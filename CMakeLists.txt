cmake_minimum_required(VERSION 3.16)
project(splatter_engine LANGUAGES CXX C)

# Build configuration
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose build type: Debug, Release, etc." FORCE)
endif()

# Build toggles
option(BUILD_ENGINE "Build C++ engine executable" ON)
option(BUILD_PY_MODULE "Build Python (Cython) extension" ON)

# Shared dependencies (available to subprojects)
include(FetchContent)
FetchContent_Declare(
    Eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(Eigen)

# Required Boost.Interprocess for shared memory
cmake_policy(SET CMP0167 NEW) # Suppress FindBoost deprecation warning
find_package(Boost 1.70 QUIET COMPONENTS interprocess)
if(Boost_FOUND)
    message(STATUS "Using system Boost.Interprocess")
else()
    message(STATUS "Boost.Interprocess not found; fetching via FetchContent")
    set(BOOST_VERSION 1.83.0 CACHE STRING "Boost release version to fetch")
    string(REPLACE "." "_" BOOST_VERSION_U ${BOOST_VERSION})
    # boost_ext provides headers
    FetchContent_Declare(
        boost_ext
        URL https://archives.boost.io/release/${BOOST_VERSION}/source/boost_${BOOST_VERSION_U}.tar.gz
        DOWNLOAD_EXTRACT_TIMESTAMP OFF
    )
    FetchContent_MakeAvailable(boost_ext)
endif()

if(BUILD_ENGINE)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/engine/CMakeLists.txt)
        add_subdirectory(engine)
    endif()
endif()

if(BUILD_PY_MODULE)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/python/CMakeLists.txt)
        add_subdirectory(python)
    endif()
endif()

# Convenience meta-target to build both when present
add_custom_target(dev ALL)
if(TARGET splatter_engine)
    add_dependencies(dev splatter_engine)
endif()
if(TARGET bridge)
    add_dependencies(dev bridge)
endif()