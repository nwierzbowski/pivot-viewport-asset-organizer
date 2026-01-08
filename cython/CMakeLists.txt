# Blender-side Cython modules (bpy/marshalling). IPC SDK is built separately in elbo_sdk.

# Load common configuration
include(${CMAKE_CURRENT_SOURCE_DIR}/../../pivot-cmake-common/PivotCommon.cmake)

# Setup Cython using common macro
_pivot_setup_cython()

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

# Build all Cython modules using common macro
if(NOT DEFINED PIVOT_BRIDGE_WHEEL_OUTPUT_DIR)
    set(PIVOT_BRIDGE_WHEEL_OUTPUT_DIR "${CMAKE_SOURCE_DIR}/dist/wheels")
endif()
_pivot_add_cython_modules("${CYTHON_MODULE_SOURCES}" "${CMAKE_CURRENT_SOURCE_DIR}/../native" "${PIVOT_BRIDGE_WHEEL_OUTPUT_DIR}")
