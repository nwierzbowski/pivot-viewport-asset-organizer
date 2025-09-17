cmake_minimum_required(VERSION 3.16)
project(splatter_engine LANGUAGES CXX C)

# Build configuration
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose build type: Debug, Release, etc." FORCE)
endif()

# Core engine sources (shared by library + bindings + executable)
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

# Build a static core to avoid duplicate compilation
add_library(splatter_engine_core STATIC ${ENGINE_SOURCES})
target_compile_features(splatter_engine_core PUBLIC cxx_std_20)
target_include_directories(splatter_engine_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/splatter/engine
)
set_property(TARGET splatter_engine_core PROPERTY POSITION_INDEPENDENT_CODE ON)
if(MSVC)
    target_compile_options(splatter_engine_core PRIVATE /W4 /permissive- /EHsc)
else()
    target_compile_options(splatter_engine_core PRIVATE -Wall -Wextra -pedantic)
endif()

# Executable linking the core
add_executable(splatter_engine splatter/engine/main.cpp)
target_link_libraries(splatter_engine PRIVATE splatter_engine_core)

# Set executable output directory to splatter/bin for clean packaging
set_target_properties(splatter_engine PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/splatter/bin
    RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_CURRENT_SOURCE_DIR}/splatter/bin
    RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_CURRENT_SOURCE_DIR}/splatter/bin
    RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_CURRENT_SOURCE_DIR}/splatter/bin
    RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_CURRENT_SOURCE_DIR}/splatter/bin
)

# Optionally build Python (Cython) extension
option(SPLATTER_BUILD_PY_EXTENSION "Build Cython Python module bridge" ON)
if(SPLATTER_BUILD_PY_EXTENSION)
    find_package(Python COMPONENTS Interpreter Development REQUIRED)
    find_package(Python3 COMPONENTS NumPy REQUIRED)
    find_program(CYTHON_EXECUTABLE cython REQUIRED)

    set(CYTHON_SOURCE ${CMAKE_CURRENT_SOURCE_DIR}/splatter/bridge.pyx)
    set(CYTHON_GENERATED_CPP ${CMAKE_CURRENT_BINARY_DIR}/bridge.cpp)
    add_custom_command(
        OUTPUT ${CYTHON_GENERATED_CPP}
        COMMAND ${CYTHON_EXECUTABLE} --cplus -I ${CMAKE_CURRENT_SOURCE_DIR} -o ${CYTHON_GENERATED_CPP} ${CYTHON_SOURCE}
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
    target_link_libraries(bridge PRIVATE Python::Python splatter_engine_core)
    target_include_directories(bridge PRIVATE ${Python3_NumPy_INCLUDE_DIRS})
    set_target_properties(bridge PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/splatter")
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
target_link_libraries(splatter_engine_core PUBLIC Eigen3::Eigen)
target_compile_definitions(splatter_engine_core PUBLIC $<$<CONFIG:Release>:NDEBUG>)

# Required Boost.Interprocess for shared memory
# Suppress FindBoost deprecation warning
cmake_policy(SET CMP0167 NEW)
# Try system Boost first
find_package(Boost 1.70 QUIET COMPONENTS interprocess)
if(Boost_FOUND)
    target_link_libraries(splatter_engine_core PUBLIC Boost::interprocess)
    message(STATUS "Using system Boost.Interprocess")
else()
    # Fallback: fetch Boost via FetchContent (required)
    message(STATUS "Boost.Interprocess not found; fetching via FetchContent")
    set(BOOST_VERSION 1.83.0 CACHE STRING "Boost release version to fetch")
    string(REPLACE "." "_" BOOST_VERSION_U ${BOOST_VERSION})
    include(FetchContent)
    FetchContent_Declare(
        boost_ext
        URL https://archives.boost.io/release/${BOOST_VERSION}/source/boost_${BOOST_VERSION_U}.tar.gz
        DOWNLOAD_EXTRACT_TIMESTAMP OFF
    )
    FetchContent_MakeAvailable(boost_ext)
    target_include_directories(splatter_engine_core PUBLIC ${boost_ext_SOURCE_DIR})
endif()
target_compile_definitions(splatter_engine_core PUBLIC SPLATTER_HAVE_BOOST_IPC=1)

# IPO / LTO when available
include(CheckIPOSupported)
check_ipo_supported(RESULT ipo_supported OUTPUT ipo_msg)
if(ipo_supported)
    set_property(TARGET splatter_engine PROPERTY INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
endif()

# Install rule
include(GNUInstallDirs)
install(TARGETS splatter_engine RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})