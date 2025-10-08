cmake_minimum_required(VERSION 3.16)
project(splatter_engine LANGUAGES CXX C)

# Build configuration
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose build type: Debug, Release, etc." FORCE)
endif()

# Build toggles
option(BUILD_ENGINE "Build C++ engine executable" ON)
option(BUILD_PY_MODULE "Build Python (Cython) extension" ON)

# Edition selection (defaults to PRO)
set(SPLATTER_EDITION "PRO" CACHE STRING "Edition to build (PRO or STANDARD)")
set_property(CACHE SPLATTER_EDITION PROPERTY STRINGS PRO STANDARD)
string(TOUPPER "${SPLATTER_EDITION}" SPLATTER_EDITION_UPPER)
set(_allowed_editions PRO STANDARD)
list(FIND _allowed_editions "${SPLATTER_EDITION_UPPER}" _edition_index)
if(_edition_index EQUAL -1)
    message(FATAL_ERROR "Invalid SPLATTER_EDITION '${SPLATTER_EDITION}'. Choose PRO or STANDARD.")
endif()
set(SPLATTER_EDITION "${SPLATTER_EDITION_UPPER}" CACHE STRING "Edition to build (PRO or STANDARD)" FORCE)
unset(_allowed_editions)
unset(_edition_index)

set(_edition_defines)
if(SPLATTER_EDITION STREQUAL "PRO")
    list(APPEND _edition_defines "SPLATTER_EDITION_PRO=1" "SPLATTER_EDITION_STANDARD=0")
else()
    list(APPEND _edition_defines "SPLATTER_EDITION_PRO=0" "SPLATTER_EDITION_STANDARD=1")
endif()

set(SPLATTER_EDITION_DEFINES "${_edition_defines}" CACHE INTERNAL "Compile definitions for the selected edition" FORCE)
set(SPLATTER_BIN_DIR "${CMAKE_CURRENT_SOURCE_DIR}/splatter/bin" CACHE INTERNAL "Engine output directory")
set(SPLATTER_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/splatter/lib" CACHE INTERNAL "Cython module output directory")

message(STATUS "Building Splatter edition: ${SPLATTER_EDITION}")

# Shared dependencies (available to subprojects)
include(FetchContent)
FetchContent_Declare(
    Eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(Eigen)

# Required Boost libs for IPC and JSON
cmake_policy(SET CMP0167 NEW) # Suppress FindBoost deprecation warning
find_package(Boost 1.75 QUIET COMPONENTS interprocess json)
if(Boost_FOUND)
    message(STATUS "Using system Boost (${Boost_VERSION})")
endif()

# If Boost headers are not found (or too old), fetch a Boost release for headers
if(NOT Boost_FOUND)
    message(STATUS "Boost (with components interprocess/json) not fully available; fetching Boost headers via FetchContent")
    set(BOOST_VERSION 1.83.0 CACHE STRING "Boost release version to fetch")
    string(REPLACE "." "_" BOOST_VERSION_U ${BOOST_VERSION})
    # boost_ext provides headers only
    FetchContent_Declare(
        boost_ext
        URL https://archives.boost.io/release/${BOOST_VERSION}/source/boost_${BOOST_VERSION_U}.tar.gz
        DOWNLOAD_EXTRACT_TIMESTAMP OFF
    )
    FetchContent_MakeAvailable(boost_ext)
endif()

# If Boost::json target is not available, fetch standalone Boost.JSON cmake project
    # We will build Boost.JSON from sources in the fetched Boost tree if the system target is unavailable.

add_subdirectory(core)

if(BUILD_ENGINE)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/engine/CMakeLists.txt)
        add_subdirectory(engine)
    endif()
endif()

if(BUILD_PY_MODULE)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/cython/CMakeLists.txt)
        add_subdirectory(cython)
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