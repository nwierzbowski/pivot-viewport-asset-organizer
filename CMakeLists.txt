cmake_minimum_required(VERSION 4.1.0)

project(blender_bridge LANGUAGES CXX)

include(FetchContent)

FetchContent_Declare(
    pivot-cmake-common
    GIT_REPOSITORY https://github.com/nwierzbowski/pivot-cmake-common.git  # Replace with actual repo URL
    GIT_TAG main  # Replace with appropriate tag or commit
)

FetchContent_Declare(
    pivot-core
    GIT_REPOSITORY https://github.com/nwierzbowski/pivot-core.git
    GIT_TAG main
)

FetchContent_MakeAvailable(pivot-cmake-common pivot-core)

# Load common Pivot configuration
include(${pivot-cmake-common_SOURCE_DIR}/cmake/PivotCommon.cmake)

# Blender-side Cython modules (data marshalling + bpy integrations) are built here.
# Platform-independent IPC and shared-memory bindings live in the sibling elbo_sdk project.

option(BUILD_PY_MODULE "Build Blender-side Python (Cython) modules" ON)

if(BUILD_PY_MODULE)
		if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/cython/CMakeLists.txt)
				add_subdirectory(cython)
		endif()
endif()

# Convenience meta-target
if(NOT TARGET dev)
	add_custom_target(dev ALL)
	if(TARGET pivot_wheel)
		add_dependencies(dev pivot_wheel)
	endif()
endif()
