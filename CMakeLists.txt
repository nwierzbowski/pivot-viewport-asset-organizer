cmake_minimum_required(VERSION 3.16)
project(pivot_engine LANGUAGES CXX C)

if(MSVC)
    # Ensure MSVC uses the static runtime consistently to avoid /MD vs /MT clashes
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

# Build configuration
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose build type: Debug, Release, etc." FORCE)
endif()

# Build toggles
option(BUILD_ENGINE "Build C++ engine executable" ON)
option(BUILD_PY_MODULE "Build Python (Cython) extension" ON)

# Edition selection (defaults to PRO)
set(PIVOT_EDITION "PRO" CACHE STRING "Edition to build (PRO or STANDARD)")
set_property(CACHE PIVOT_EDITION PROPERTY STRINGS PRO STANDARD)
string(TOUPPER "${PIVOT_EDITION}" PIVOT_EDITION_UPPER)
set(_allowed_editions PRO STANDARD)
list(FIND _allowed_editions "${PIVOT_EDITION_UPPER}" _edition_index)
if(_edition_index EQUAL -1)
    message(FATAL_ERROR "Invalid PIVOT_EDITION '${PIVOT_EDITION}'. Choose PRO or STANDARD.")
endif()
set(PIVOT_EDITION "${PIVOT_EDITION_UPPER}" CACHE STRING "Edition to build (PRO or STANDARD)" FORCE)
unset(_allowed_editions)
unset(_edition_index)

set(_edition_defines)
if(PIVOT_EDITION STREQUAL "PRO")
    list(APPEND _edition_defines "PIVOT_EDITION_PRO")
    set(_edition_pro_flag 1)
    set(_edition_standard_flag 0)
else()
    list(APPEND _edition_defines "PIVOT_EDITION_STANDARD")
    set(_edition_pro_flag 0)
    set(_edition_standard_flag 1)
endif()

list(APPEND _edition_defines "PIVOT_EDITION_NAME=\"${PIVOT_EDITION}\"")

set(PIVOT_EDITION_DEFINES "${_edition_defines}" CACHE INTERNAL "Compile definitions for the selected edition" FORCE)
set(PIVOT_EDITION_PRO_DEF ${_edition_pro_flag} CACHE INTERNAL "Cython DEF flag for PRO edition" FORCE)
set(PIVOT_EDITION_STANDARD_DEF ${_edition_standard_flag} CACHE INTERNAL "Cython DEF flag for STANDARD edition" FORCE)
set(PIVOT_EDITION_NAME_DEF ${PIVOT_EDITION} CACHE INTERNAL "Cython DEF name for selected edition" FORCE)

# Detect platform architecture for per-architecture builds
string(TOLOWER "${CMAKE_SYSTEM_NAME}" _system_name)
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _processor)

# Normalize architecture names
if(_processor MATCHES "^(x86_64|AMD64|amd64)$")
    set(_arch "x86-64")
elseif(_processor MATCHES "^(aarch64|arm64)$")
    set(_arch "arm64")
else()
    set(_arch "${_processor}")
endif()

set(PIVOT_PLATFORM_ID "${_system_name}-${_arch}" CACHE INTERNAL "Platform identifier (e.g., darwin-arm64, linux-x86-64)")
set(PIVOT_BIN_DIR "${CMAKE_CURRENT_SOURCE_DIR}/pivot/bin/${PIVOT_PLATFORM_ID}" CACHE INTERNAL "Engine output directory")
set(PIVOT_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/pivot/lib/${PIVOT_PLATFORM_ID}" CACHE INTERNAL "Cython module output directory")

unset(_edition_pro_flag)
unset(_edition_standard_flag)
unset(_edition_name)
unset(_system_name)
unset(_processor)
unset(_arch)
message(STATUS "Building Pivot edition: ${PIVOT_EDITION}")
message(STATUS "Platform identifier: ${PIVOT_PLATFORM_ID}")

# Ensure output directories are ready for this edition and platform
function(_pivot_prepare_dir dir platform_id)
    if(dir STREQUAL "")
        return()
    endif()
    file(MAKE_DIRECTORY "${dir}")
    # Store both the edition and platform ID in the marker file
    set(marker "${dir}/.edition")
    set(marker_content "${platform_id}:${PIVOT_EDITION}")
    set(should_clean TRUE)
    if(EXISTS "${marker}")
        file(READ "${marker}" existing_marker)
        string(STRIP "${existing_marker}" existing_marker)
        if(existing_marker STREQUAL "${marker_content}")
            set(should_clean FALSE)
        endif()
    endif()
    # Always clear to ensure correct edition artifacts
    if(should_clean)
        file(GLOB children LIST_DIRECTORIES true "${dir}/*")
        if(children)
            file(REMOVE_RECURSE ${children})
        endif()
    endif()
    file(WRITE "${marker}" "${marker_content}\n")
endfunction()

_pivot_prepare_dir("${PIVOT_BIN_DIR}" "${PIVOT_PLATFORM_ID}")
_pivot_prepare_dir("${PIVOT_LIB_DIR}" "${PIVOT_PLATFORM_ID}")

# Shared dependencies (available to subprojects)
include(FetchContent)
# Disable Eigen extras we don't use; keeps Windows builds from probing Fortran toolchains
set(BUILD_TESTING OFF CACHE BOOL "Disable all third-party test targets" FORCE)
set(EIGEN_TEST_FORTRAN OFF CACHE BOOL "Disable Eigen Fortran tests" FORCE)
set(EIGEN_BUILD_TESTING OFF CACHE BOOL "Disable Eigen self-tests" FORCE)
set(EIGEN_BUILD_DOC OFF CACHE BOOL "Disable Eigen documentation build" FORCE)
FetchContent_Declare(
    Eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_GetProperties(Eigen)
if(NOT Eigen_POPULATED)
    FetchContent_Populate(Eigen)
endif()
if(NOT DEFINED Eigen_SOURCE_DIR AND DEFINED eigen_SOURCE_DIR)
    set(Eigen_SOURCE_DIR "${eigen_SOURCE_DIR}")
endif()

if(NOT TARGET Eigen3::Eigen)
    add_library(Eigen3::Eigen INTERFACE IMPORTED GLOBAL)
    set_target_properties(Eigen3::Eigen PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${Eigen_SOURCE_DIR}"
    )
endif()

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
if(TARGET pivot_engine)
    add_dependencies(dev pivot_engine)
endif()
if(TARGET bridge)
    add_dependencies(dev bridge)
endif()