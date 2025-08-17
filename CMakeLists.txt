# CMakeLists.txt

cmake_minimum_required(VERSION 3.12)

# Set the C and C++ compilers to specific versions
set(CMAKE_C_COMPILER "gcc-11")
set(CMAKE_CXX_COMPILER "g++-11")

# Now that the compiler is set, initialize the project.
project(MyEngine CXX C) # Explicitly enable C++ and C

# Create a SHARED library (.so/.dll/.pyd) from our source files
add_library(engine SHARED
    my_addon/engine/engine.cpp
)

# Tell CMake where to find the header files
target_include_directories(engine PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/splatter/engine
)