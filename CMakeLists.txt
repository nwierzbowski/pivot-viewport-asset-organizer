cmake_minimum_required(VERSION 3.16)
project(splatter_engine LANGUAGES CXX C)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose build type: Debug, Release, etc." FORCE)
endif()

find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_program(CYTHON_EXECUTABLE cython REQUIRED)

set(ENGINE_SOURCES
    splatter/engine/engine.cpp
    splatter/engine/share/stats.cpp
    splatter/engine/object/computation/voxel.cpp
    splatter/engine/object/computation/wire_detect.cpp
    splatter/engine/object/util/linalg3.cpp
    splatter/engine/object/computation/cog.cpp
    splatter/engine/object/analysis/analysis.cpp
)

add_library(splatter_engine SHARED ${ENGINE_SOURCES})

target_compile_options(splatter_engine PRIVATE
    -Wall           # Turn on all standard warnings
    -Wextra         # Turn on even more warnings
    -pedantic       # Enforce strict standard compliance, disallow compiler extensions
)

target_compile_features(splatter_engine PRIVATE cxx_std_20)
target_include_directories(splatter_engine PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/splatter/engine
)

include(FetchContent)
FetchContent_Declare(
    Eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0 
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(Eigen)

target_link_libraries(splatter_engine PUBLIC Eigen3::Eigen)
target_compile_definitions(splatter_engine PRIVATE
    $<$<CONFIG:Release>:NDEBUG>
)
# Optimizations IPO is let compiler have global view for more aggressive opts
include(CheckIPOSupported)
check_ipo_supported(RESULT ipo_supported OUTPUT ipo_msg)
if(ipo_supported)
  set_property(TARGET splatter_engine PROPERTY INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
endif()

set(CYTHON_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/splatter/bridge.pyx")
set(CYTHON_GENERATED_CPP "${CMAKE_CURRENT_BINARY_DIR}/bridge.cpp")

add_custom_command(
    OUTPUT ${CYTHON_GENERATED_CPP}
    COMMAND ${CYTHON_EXECUTABLE}
        --cplus
        -I ${CMAKE_CURRENT_SOURCE_DIR}
        -o ${CYTHON_GENERATED_CPP}
        ${CYTHON_SOURCE}
    DEPENDS ${CYTHON_SOURCE}
    COMMENT "Cythonizing ${CYTHON_SOURCE}"
)

add_library(bridge MODULE ${CYTHON_GENERATED_CPP})

set_target_properties(bridge PROPERTIES PREFIX "")

if(WIN32)
    set_target_properties(bridge PROPERTIES SUFFIX ".pyd")
else()
    set_target_properties(bridge PROPERTIES SUFFIX ".so")
endif()

target_link_libraries(bridge PRIVATE
    Python::Python
    splatter_engine
)

set_target_properties(bridge PROPERTIES LIBRARY_OUTPUT_DIRECTORY
    "${CMAKE_CURRENT_SOURCE_DIR}/splatter"
)


#   target_compile_options(splatter_engine PRIVATE $<$<CONFIG:Release>:-Ofast -ffast-math>)
#   target_compile_options(bridge         PRIVATE $<$<CONFIG:Release>:-Ofast -ffast-math>)
