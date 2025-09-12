cmake_minimum_required(VERSION 3.16)
project(splatter_engine LANGUAGES CXX C)

# Build configuration
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose build type: Debug, Release, etc." FORCE)
endif()

# Core engine sources
set(ENGINE_SOURCES
    splatter/engine/engine.cpp
    splatter/engine/share/stats.cpp
    splatter/engine/object/computation/voxel.cpp
    splatter/engine/object/computation/wire_detect.cpp
    splatter/engine/object/computation/cog.cpp
    splatter/engine/object/computation/b_box.cpp
    splatter/engine/object/analysis/ground.cpp
    splatter/engine/object/analysis/wall.cpp
    splatter/engine/object/util/linalg3.cpp
)

# Executable only (removed Python/Cython bindings)
add_executable(splatter_engine_exec
    ${ENGINE_SOURCES}
    splatter/engine/main.cpp
)

target_compile_features(splatter_engine_exec PRIVATE cxx_std_20)
target_include_directories(splatter_engine_exec PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/splatter/engine
)

if(MSVC)
    target_compile_options(splatter_engine_exec PRIVATE /W4 /permissive- /EHsc)
else()
    target_compile_options(splatter_engine_exec PRIVATE -Wall -Wextra -pedantic)
endif()

# Dependencies
include(FetchContent)
FetchContent_Declare(
    Eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(Eigen)
target_link_libraries(splatter_engine_exec PRIVATE Eigen3::Eigen)
target_compile_definitions(splatter_engine_exec PRIVATE $<$<CONFIG:Release>:NDEBUG>)

# IPO / LTO when available
include(CheckIPOSupported)
check_ipo_supported(RESULT ipo_supported OUTPUT ipo_msg)
if(ipo_supported)
    set_property(TARGET splatter_engine_exec PROPERTY INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
endif()

# Install rule
include(GNUInstallDirs)
install(TARGETS splatter_engine_exec RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})