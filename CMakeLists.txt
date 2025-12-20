cmake_minimum_required(VERSION 3.20)
project(approximate_model_counting VERSION 0.1.0 LANGUAGES C CXX)

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
    GIT_TAG rel-2.2.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(cadical)

# Generate build.hpp for CaDiCaL (in src directory)
file(WRITE "${cadical_SOURCE_DIR}/src/build.hpp"
"#ifndef _build_hpp_INCLUDED
#define _build_hpp_INCLUDED
#define VERSION \"2.2.0\"
#define IDENTIFIER \"unknown\"
#define COMPILER \"${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}\"
#define FLAGS \"${CMAKE_CXX_FLAGS}\"
#define DATE \"${CMAKE_CURRENT_LIST_FILE}\"
#endif
")

# Build CaDiCaL library with both C and C++ files
file(GLOB CADICAL_CPP_SOURCES "${cadical_SOURCE_DIR}/src/*.cpp")
file(GLOB CADICAL_C_SOURCES "${cadical_SOURCE_DIR}/src/*.c")
# Exclude files with main functions
list(FILTER CADICAL_CPP_SOURCES EXCLUDE REGEX ".*cadical\\.cpp$")
list(FILTER CADICAL_CPP_SOURCES EXCLUDE REGEX ".*mobical\\.cpp$")

add_library(cadical STATIC ${CADICAL_CPP_SOURCES} ${CADICAL_C_SOURCES})
target_include_directories(cadical PUBLIC ${cadical_SOURCE_DIR}/src)
target_compile_options(cadical PRIVATE -w)  # Suppress CaDiCaL warnings
target_compile_definitions(cadical PRIVATE NCLOSEFROM)  # Disable closefrom (not available on macOS)

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
    src/solution_table.cpp
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

# Test internals module (for testing C++ code not exposed to Python)
pybind11_add_module(_test_internals
    tests/cpp/test_bitvector.cpp
)

target_link_libraries(_test_internals PRIVATE amc_core)

install(TARGETS _test_internals
    LIBRARY DESTINATION tests
)
