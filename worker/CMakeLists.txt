cmake_minimum_required(VERSION 3.20)
project(autoroad_worker CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)


set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG -flto=auto -ffast-math -funroll-loops -fomit-frame-pointer" CACHE STRING "Release flags" FORCE)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)

# Find OR-Tools
find_package(ortools CONFIG REQUIRED)

# Find nlohmann_json for JSON parsing
find_package(nlohmann_json REQUIRED)

# Fetch cpp-httplib
include(FetchContent)
FetchContent_Declare(
    httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG v0.15.3
)
FetchContent_MakeAvailable(httplib)

# Main executable
add_executable(worker
    src/main.cpp
    src/solver.cpp
)

target_link_libraries(worker
    ortools::ortools
    nlohmann_json::nlohmann_json
    httplib::httplib
)

target_include_directories(worker PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
