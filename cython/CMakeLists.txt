# Python (Cython) module subproject

find_package(Python3 COMPONENTS Interpreter Development.Module NumPy REQUIRED)
find_program(CYTHON_EXECUTABLE cython REQUIRED)

set(CYTHON_SOURCE ${CMAKE_CURRENT_SOURCE_DIR}/operators/classify/classify_object.pyx)
set(CYTHON_MODULES
    selection_utils
    shm_utils
    transform_utils
    classification
)
set(CYTHON_MODULE_SOURCES
    shared/selection_utils.pyx
    shared/shm_utils.pyx
    shared/transform_utils.pyx
    classification.pyx
)
set(CYTHON_INCLUDES
    ${CMAKE_CURRENT_SOURCE_DIR}/shared/selection_utils.pxd
    ${CMAKE_CURRENT_SOURCE_DIR}/shared/shm_utils.pxd
    ${CMAKE_CURRENT_SOURCE_DIR}/shared/transform_utils.pxd
)
set(CYTHON_GENERATED_CPP ${CMAKE_CURRENT_BINARY_DIR}/bridge.cpp)

add_custom_command(
    OUTPUT ${CYTHON_GENERATED_CPP}
    COMMAND ${CYTHON_EXECUTABLE} --cplus --module-name=bridge -a -I ${CMAKE_CURRENT_SOURCE_DIR} -I ${CMAKE_CURRENT_SOURCE_DIR}/.. -o ${CYTHON_GENERATED_CPP} ${CYTHON_SOURCE}
    BYPRODUCTS ${CMAKE_CURRENT_BINARY_DIR}/bridge.html
    DEPENDS ${CYTHON_SOURCE} ${CYTHON_INCLUDES}
    COMMENT "Cythonizing ${CYTHON_SOURCE} with HTML annotations"
)

add_library(bridge MODULE ${CYTHON_GENERATED_CPP})
set_target_properties(bridge PROPERTIES PREFIX "")

# Correct platform-specific suffix is handled by Python3::Module on most platforms
if(WIN32)
    set_target_properties(bridge PROPERTIES SUFFIX ".pyd")
endif()

target_link_libraries(bridge PRIVATE Python3::Module)

# Numpy headers
if(Python3_NumPy_INCLUDE_DIRS)
    target_include_directories(bridge PRIVATE ${Python3_NumPy_INCLUDE_DIRS})
endif()

# Include engine src for classification.h
target_include_directories(bridge PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../core)

# Link core library
target_link_libraries(bridge PRIVATE core)

# Build helper modules (selection_utils, shm_utils, transform_utils, surface_types)
foreach(mod_src ${CYTHON_MODULE_SOURCES})
    # Extract module name from path
    get_filename_component(mod ${mod_src} NAME_WE)
    set(SRC ${CMAKE_CURRENT_SOURCE_DIR}/${mod_src})
    set(OUT ${CMAKE_CURRENT_BINARY_DIR}/${mod}.cpp)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/${mod_src})
        set(PXD_FILE ${CMAKE_CURRENT_SOURCE_DIR}/${mod}.pxd)
        if(EXISTS ${PXD_FILE})
            add_custom_command(
                OUTPUT ${OUT}
                COMMAND ${CYTHON_EXECUTABLE} --cplus -a -I ${CMAKE_CURRENT_SOURCE_DIR} -I ${CMAKE_CURRENT_SOURCE_DIR}/.. -o ${OUT} ${SRC}
                BYPRODUCTS ${CMAKE_CURRENT_BINARY_DIR}/${mod}.html
                DEPENDS ${SRC} ${PXD_FILE}
                COMMENT "Cythonizing ${SRC} with HTML annotations"
            )
        else()
            add_custom_command(
                OUTPUT ${OUT}
                COMMAND ${CYTHON_EXECUTABLE} --cplus -a -I ${CMAKE_CURRENT_SOURCE_DIR} -I ${CMAKE_CURRENT_SOURCE_DIR}/.. -o ${OUT} ${SRC}
                BYPRODUCTS ${CMAKE_CURRENT_BINARY_DIR}/${mod}.html
                DEPENDS ${SRC}
                COMMENT "Cythonizing ${SRC} with HTML annotations"
            )
        endif()
        add_library(${mod} MODULE ${OUT})
        set_target_properties(${mod} PROPERTIES PREFIX "")
        if(WIN32)
            set_target_properties(${mod} PROPERTIES SUFFIX ".pyd")
        endif()
        target_link_libraries(${mod} PRIVATE Python3::Module)
        # Numpy headers
        if(Python3_NumPy_INCLUDE_DIRS)
            target_include_directories(${mod} PRIVATE ${Python3_NumPy_INCLUDE_DIRS})
        endif()
        # Include engine src for classification.h (needed for surface_types)
        target_include_directories(${mod} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../core)
    endif()
endforeach()

# Consolidate output directory for all Cython modules
set(CYTHON_ALL_MODULES bridge ${CYTHON_MODULES})
foreach(mod ${CYTHON_ALL_MODULES})
    set_target_properties(${mod} PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../splatter/lib")
endforeach()
