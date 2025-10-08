# Python (Cython) module subproject

find_package(Python3 COMPONENTS Interpreter Development.Module NumPy REQUIRED)
find_program(CYTHON_EXECUTABLE cython REQUIRED)

set(EDITION_FLAGS_TEMPLATE ${CMAKE_CURRENT_SOURCE_DIR}/edition_flags.pxi.in)
set(EDITION_FLAGS_FILE ${CMAKE_CURRENT_BINARY_DIR}/edition_flags.pxi)
configure_file(${EDITION_FLAGS_TEMPLATE} ${EDITION_FLAGS_FILE} @ONLY)

set(CYTHON_MODULE_SOURCES
    operators/classify_object.pyx
    shared/classification.pyx
    shared/edition_utils.pyx
    shared/selection_utils.pyx
    shared/shm_utils.pyx
    shared/transform_utils.pyx
)

# Operator modules that need linking to core library
set(OPERATOR_MODULES classify_object classification)

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
                COMMAND ${CYTHON_EXECUTABLE} --cplus -a -I ${CMAKE_CURRENT_BINARY_DIR} -I ${CMAKE_CURRENT_SOURCE_DIR} -I ${CMAKE_CURRENT_SOURCE_DIR}/.. -o ${OUT} ${SRC}
                BYPRODUCTS ${CMAKE_CURRENT_BINARY_DIR}/${mod}.html
                DEPENDS ${SRC} ${PXD_FILE} ${EDITION_FLAGS_FILE}
                COMMENT "Cythonizing ${SRC} with HTML annotations"
            )
        else()
            add_custom_command(
                OUTPUT ${OUT}
                COMMAND ${CYTHON_EXECUTABLE} --cplus -a -I ${CMAKE_CURRENT_BINARY_DIR} -I ${CMAKE_CURRENT_SOURCE_DIR} -I ${CMAKE_CURRENT_SOURCE_DIR}/.. -o ${OUT} ${SRC}
                BYPRODUCTS ${CMAKE_CURRENT_BINARY_DIR}/${mod}.html
                DEPENDS ${SRC} ${EDITION_FLAGS_FILE}
                COMMENT "Cythonizing ${SRC} with HTML annotations"
            )
        endif()
        add_library(${mod} MODULE ${OUT})
        set_target_properties(${mod} PROPERTIES PREFIX "")
        if(WIN32)
            set_target_properties(${mod} PROPERTIES SUFFIX ".pyd")
        endif()
        if(TARGET splatter_ensure_outputs)
            add_dependencies(${mod} splatter_ensure_outputs)
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
        if(DEFINED SPLATTER_EDITION_DEFINES)
            foreach(def ${SPLATTER_EDITION_DEFINES})
                target_compile_definitions(${mod} PRIVATE ${def})
            endforeach()
        endif()
        # Force rebuild on edition switch by removing old module
        add_custom_command(TARGET ${mod} PRE_BUILD
            COMMAND ${CMAKE_COMMAND} -E remove $<TARGET_FILE:${mod}>
            COMMENT "Removing old Cython module to force rebuild on edition switch"
        )
    endif()
endforeach()

# Consolidate output directory for all Cython modules
if(DEFINED SPLATTER_LIB_DIR)
    set(_cython_output_dir ${SPLATTER_LIB_DIR})
else()
    set(_cython_output_dir "${CMAKE_CURRENT_SOURCE_DIR}/../splatter/lib")
endif()

set(CYTHON_ALL_MODULES)
foreach(mod_src ${CYTHON_MODULE_SOURCES})
    get_filename_component(mod ${mod_src} NAME_WE)
    list(APPEND CYTHON_ALL_MODULES ${mod})
endforeach()
foreach(mod ${CYTHON_ALL_MODULES})
    if(TARGET ${mod})
        set_target_properties(${mod} PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${_cython_output_dir}")
    endif()
endforeach()

unset(_cython_output_dir)
