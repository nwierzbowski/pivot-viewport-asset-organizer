# Python (Cython) module subproject

find_package(Python3 COMPONENTS Interpreter Development.Module NumPy REQUIRED)
find_program(CYTHON_EXECUTABLE cython REQUIRED)

set(CYTHON_MODULE_SOURCES
    operators/classify_object.pyx
    shared/selection_utils.pyx
    shared/shm_utils.pyx
    shared/transform_utils.pyx
)
# Operator modules that need linking to core library
set(OPERATOR_MODULES classify_object)
set(CYTHON_INCLUDES
)

# Build all Cython modules
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
        # Include engine src for classification.h (needed for operator modules)
        target_include_directories(${mod} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../core)
        # Link core library for operator modules
        if(${mod} IN_LIST OPERATOR_MODULES)
            target_link_libraries(${mod} PRIVATE core)
        endif()
    endif()
endforeach()

# Consolidate output directory for all Cython modules
set(CYTHON_ALL_MODULES)
foreach(mod_src ${CYTHON_MODULE_SOURCES})
    get_filename_component(mod ${mod_src} NAME_WE)
    list(APPEND CYTHON_ALL_MODULES ${mod})
endforeach()
foreach(mod ${CYTHON_ALL_MODULES})
    set_target_properties(${mod} PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../splatter/lib")
endforeach()
