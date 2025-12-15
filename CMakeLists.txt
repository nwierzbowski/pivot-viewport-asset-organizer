cmake_minimum_required(VERSION 3.16)

# Set minimum macOS deployment target
if(APPLE)
    set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "Minimum macOS version" FORCE)
endif()

project(pivot_bridge LANGUAGES CXX)

# ---------------------------------------------------------------------------
# SYSTEM COMPATIBILITY SETTINGS
# ---------------------------------------------------------------------------

# Windows: Force compatibility with Windows 8.1 (Blender minimum)
if(WIN32)
    add_compile_definitions(_WIN32_WINNT=0x0603 WINVER=0x0603)
endif()

if(MSVC)
    # Ensure MSVC uses the static runtime (matches engine build /MT)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

# Build configuration
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose build type: Debug, Release, etc." FORCE)
endif()

# Build toggles
option(BUILD_PY_MODULE "Build Python (Cython) extension" ON)

# Edition selection (inherit from parent or default to PRO)
if(NOT DEFINED PIVOT_EDITION)
    set(PIVOT_EDITION "PRO" CACHE STRING "Edition to build (PRO or STANDARD)")
endif()
set_property(CACHE PIVOT_EDITION PROPERTY STRINGS PRO STANDARD)
string(TOUPPER "${PIVOT_EDITION}" PIVOT_EDITION_UPPER)
set(_allowed_editions PRO STANDARD)
list(FIND _allowed_editions "${PIVOT_EDITION_UPPER}" _edition_index)
if(_edition_index EQUAL -1)
    message(FATAL_ERROR "Invalid PIVOT_EDITION '${PIVOT_EDITION}'. Choose PRO or STANDARD.")
endif()
set(PIVOT_EDITION "${PIVOT_EDITION_UPPER}" CACHE STRING "Edition to build (PRO or STANDARD)" FORCE)

# Define edition flags
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

# Cache internal variables for subdirectories
if(NOT DEFINED PIVOT_EDITION_DEFINES)
    set(PIVOT_EDITION_DEFINES "${_edition_defines}" CACHE INTERNAL "Compile definitions for the selected edition" FORCE)
endif()
if(NOT DEFINED PIVOT_EDITION_PRO_DEF)
    set(PIVOT_EDITION_PRO_DEF ${_edition_pro_flag} CACHE INTERNAL "Cython DEF flag for PRO edition" FORCE)
endif()
if(NOT DEFINED PIVOT_EDITION_STANDARD_DEF)
    set(PIVOT_EDITION_STANDARD_DEF ${_edition_standard_flag} CACHE INTERNAL "Cython DEF flag for STANDARD edition" FORCE)
endif()
if(NOT DEFINED PIVOT_EDITION_NAME_DEF)
    set(PIVOT_EDITION_NAME_DEF ${PIVOT_EDITION} CACHE INTERNAL "Cython DEF name for selected edition" FORCE)
endif()

# Detect platform architecture
string(TOLOWER "${CMAKE_SYSTEM_NAME}" _system_name)
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _processor)

if(_processor MATCHES "^(x86_64|AMD64|amd64)$")
    set(_arch "x86-64")
elseif(_processor MATCHES "^(aarch64|arm64)$")
    set(_arch "arm64")
else()
    set(_arch "${_processor}")
endif()

set(PIVOT_PLATFORM_ID "${_system_name}-${_arch}" CACHE INTERNAL "Platform identifier")
# Cython modules are output directly to pivot_lib/ for wheel building (not to pivot/lib/)
# This avoids Blender's policy violation for top-level modules in extension directory
if(NOT DEFINED PIVOT_BIN_DIR)
    set(PIVOT_BIN_DIR "${CMAKE_CURRENT_SOURCE_DIR}/pivot/bin/${PIVOT_PLATFORM_ID}" CACHE INTERNAL "Engine output directory")
endif()

message(STATUS "Building Pivot edition: ${PIVOT_EDITION}")
message(STATUS "Platform identifier: ${PIVOT_PLATFORM_ID}")

# Prepare output directories
function(_pivot_prepare_dir dir platform_id)
    if(dir STREQUAL "")
        return()
    endif()
    file(MAKE_DIRECTORY "${dir}")
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
    if(should_clean)
        file(GLOB entries "${dir}/*")
        if(entries)
            file(REMOVE_RECURSE ${entries})
        endif()
    endif()
    file(WRITE "${marker}" "${marker_content}\n")
endfunction()


_pivot_prepare_dir("${PIVOT_BIN_DIR}" "${PIVOT_PLATFORM_ID}")

# Required Boost libs for IPC
cmake_policy(SET CMP0167 NEW) 
find_package(Boost 1.75 QUIET COMPONENTS interprocess)
if(Boost_FOUND)
    message(STATUS "Using system Boost (${Boost_VERSION})")
else()
    message(STATUS "Boost not fully available; fetching headers via FetchContent")
    include(FetchContent)
    set(BOOST_VERSION 1.83.0 CACHE STRING "Boost release version to fetch")
    string(REPLACE "." "_" BOOST_VERSION_U ${BOOST_VERSION})
    FetchContent_Declare(
        boost_ext
        URL https://archives.boost.io/release/${BOOST_VERSION}/source/boost_${BOOST_VERSION_U}.tar.gz
        DOWNLOAD_EXTRACT_TIMESTAMP OFF
    )
    FetchContent_MakeAvailable(boost_ext)
endif()

# Build Cython Subdirectory
if(BUILD_PY_MODULE)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/cython/CMakeLists.txt)
        add_subdirectory(cython)
    endif()
endif()

# Convenience meta-target
if(NOT TARGET dev)
  add_custom_target(dev ALL)
  if(TARGET bridge)
    add_dependencies(dev bridge)
  endif()
endif()