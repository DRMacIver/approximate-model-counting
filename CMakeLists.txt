cmake_minimum_required(VERSION 3.20)
project(approximate_model_counting VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Build position-independent code
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Coverage flags
option(ENABLE_COVERAGE "Enable coverage reporting" OFF)
if(ENABLE_COVERAGE)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --coverage")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} --coverage")
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} --coverage")
endif()

include(FetchContent)

# Fetch CaDiCaL source
FetchContent_Declare(
    cadical
    GIT_REPOSITORY https://github.com/arminbiere/cadical.git
    GIT_TAG rel-2.1.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(cadical)

# Create build directory and generate build.hpp
set(CADICAL_BUILD_DIR "${cadical_SOURCE_DIR}/build")
file(MAKE_DIRECTORY ${CADICAL_BUILD_DIR})

# Generate a minimal build.hpp for CaDiCaL
if(NOT EXISTS "${CADICAL_BUILD_DIR}/build.hpp")
    file(WRITE "${CADICAL_BUILD_DIR}/build.hpp" "
#ifndef _build_hpp_INCLUDED
#define _build_hpp_INCLUDED
#define VERSION \"2.1.0\"
#define IDENTIFIER \"unknown\"
#define COMPILER \"${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}\"
#define FLAGS \"${CMAKE_CXX_FLAGS}\"
#define DATE \"${CMAKE_CURRENT_LIST_FILE}\"
#endif
")
endif()

# Build CaDiCaL by compiling its source files directly
file(GLOB CADICAL_SOURCES "${cadical_SOURCE_DIR}/src/*.cpp")
add_library(cadical STATIC ${CADICAL_SOURCES})
target_include_directories(cadical PUBLIC
    ${cadical_SOURCE_DIR}/src
    ${CADICAL_BUILD_DIR}
)
target_compile_options(cadical PRIVATE -w)  # Suppress CaDiCaL warnings

# Fetch pybind11
FetchContent_Declare(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG v2.13.6
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(pybind11)

# Core library
add_library(amc_core STATIC
    src/solution_information.cpp
)

target_include_directories(amc_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${cadical_SOURCE_DIR}/src
)

target_link_libraries(amc_core PUBLIC cadical)

# Python bindings
pybind11_add_module(_approximate_model_counting
    bindings/python_bindings.cpp
)

target_link_libraries(_approximate_model_counting PRIVATE amc_core)

# Install the Python module
install(TARGETS _approximate_model_counting
    LIBRARY DESTINATION approximate_model_counting
)
