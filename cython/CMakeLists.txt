# Blender-side Cython modules (bpy/marshalling). IPC SDK is built separately in elbo_sdk.

# Load common configuration
include(${CMAKE_CURRENT_SOURCE_DIR}/../pivot-cmake-common/cmake/PivotCommon.cmake)

pivot_common_cython_find_python()

set(CYTHON_MODULE_SOURCES
    operators/standardize.pyx
    shared/classification.pyx
    shared/collection_manager.pyx
    shared/edition_utils.pyx
    shared/engine_state.pyx
    shared/group_manager.pyx
    shared/selection_utils.pyx
    shared/shm_utils.pyx
    shared/surface_manager.pyx
)

set(PIVOT_WHEEL_PKG_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../native")
set(PIVOT_WHEEL_OUTPUT_DIR "${PROJECT_SOURCE_DIR}/dist/wheels/${PIVOT_PLATFORM_ID}/${PIVOT_EDITION}")

file(MAKE_DIRECTORY "${PIVOT_WHEEL_PKG_DIR}")
file(MAKE_DIRECTORY "${PIVOT_WHEEL_OUTPUT_DIR}")

set(EDITION_FLAGS_TEMPLATE "${CMAKE_CURRENT_SOURCE_DIR}/edition_flags.pxi.in")
set(EDITION_FLAGS_FILE "${CMAKE_CURRENT_BINARY_DIR}/edition_flags.pxi")
if(EXISTS "${EDITION_FLAGS_TEMPLATE}")
    if(PIVOT_EDITION STREQUAL "PRO")
        set(PIVOT_EDITION_PRO_DEF 1)
        set(PIVOT_EDITION_STANDARD_DEF 0)
    else()
        set(PIVOT_EDITION_PRO_DEF 0)
        set(PIVOT_EDITION_STANDARD_DEF 1)
    endif()
    configure_file("${EDITION_FLAGS_TEMPLATE}" "${EDITION_FLAGS_FILE}" @ONLY)
endif()

set(_pivot_edition_defines)
if(PIVOT_EDITION STREQUAL "PRO")
    list(APPEND _pivot_edition_defines PIVOT_EDITION_PRO)
else()
    list(APPEND _pivot_edition_defines PIVOT_EDITION_STANDARD)
endif()
list(APPEND _pivot_edition_defines PIVOT_EDITION_NAME="${PIVOT_EDITION}")

set(_cython_common_includes
    "${CMAKE_CURRENT_BINARY_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
    ${Python3_INCLUDE_DIRS}
)
if(Python3_NumPy_INCLUDE_DIRS)
    list(APPEND _cython_common_includes ${Python3_NumPy_INCLUDE_DIRS})
endif()
if(_Python3_NumPy_INCLUDE_DIR)
    list(APPEND _cython_common_includes ${_Python3_NumPy_INCLUDE_DIR})
endif()

set(_pivot_core_include_candidates
    "${CMAKE_CURRENT_SOURCE_DIR}/../../elbo-sdk/pivot-core"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../core"
)
foreach(_cand IN LISTS _pivot_core_include_candidates)
    if(EXISTS "${_cand}/classification.h")
        list(APPEND _cython_common_includes "${_cand}")
        break()
    endif()
endforeach()

if(EXISTS "${EDITION_FLAGS_FILE}")
    list(APPEND _cython_common_includes "${CMAKE_CURRENT_BINARY_DIR}")
endif()

list(REMOVE_DUPLICATES _cython_common_includes)

pivot_common_cython_create_modules(
    MODULE_SOURCES ${CYTHON_MODULE_SOURCES}
    PYX_ROOT "${CMAKE_CURRENT_SOURCE_DIR}"
    BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}"
    INCLUDE_DIRS ${_cython_common_includes}
    DEFINES ${_pivot_edition_defines}
    WHEEL_PKG_DIR "${PIVOT_WHEEL_PKG_DIR}"
    MODULE_TARGETS_VAR _pivot_all_modules
)

pivot_common_cython_create_wheel_target(
    TARGET_NAME pivot_wheel
    SCRIPT_PATH "${PROJECT_SOURCE_DIR}/build_wheel.py"
    OUTPUT_DIR "${PIVOT_WHEEL_OUTPUT_DIR}"
    MODULE_TARGETS ${_pivot_all_modules}
)
