cmake_minimum_required(VERSION 3.10)
project(lcmware_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(LCM REQUIRED lcm)

# Include directories
include_directories(
    ${LCM_INCLUDE_DIRS}
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/lcmware/types
)

# Link directories
link_directories(${LCM_LIBRARY_DIRS})

# Collect all LCM type headers
file(GLOB_RECURSE LCM_TYPE_HEADERS 
    "${CMAKE_CURRENT_SOURCE_DIR}/lcmware/types/**/*.hpp"
)

# Create header-only library
add_library(lcmware INTERFACE)

target_include_directories(lcmware INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/lcmware/types>
    $<INSTALL_INTERFACE:include>
    $<INSTALL_INTERFACE:include/lcmware/types>
    ${LCM_INCLUDE_DIRS}
)

target_link_libraries(lcmware INTERFACE
    ${LCM_LIBRARIES}
)

target_compile_options(lcmware INTERFACE
    ${LCM_CFLAGS_OTHER}
)

# Install headers
install(FILES
    lcmware/constants.hpp
    lcmware/manager.hpp
    lcmware/topic.hpp
    lcmware/service.hpp  
    lcmware/action.hpp
    DESTINATION include/lcmware
)

install(DIRECTORY lcmware/types/
    DESTINATION include/lcmware/types
    FILES_MATCHING PATTERN "*.hpp"
)

# Install CMake config
install(TARGETS lcmware
    EXPORT lcmware-targets
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(EXPORT lcmware-targets
    FILE lcmware-targets.cmake
    DESTINATION lib/cmake/lcmware
)

# Create and install package config file
include(CMakePackageConfigHelpers)
write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/lcmware-config-version.cmake"
    VERSION 1.0.0
    COMPATIBILITY SameMajorVersion
)

configure_package_config_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/lcmware-config.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/lcmware-config.cmake"
    INSTALL_DESTINATION lib/cmake/lcmware
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/lcmware-config.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/lcmware-config-version.cmake"
    DESTINATION lib/cmake/lcmware
)

# Examples (optional)
option(BUILD_EXAMPLES "Build example programs" OFF)

if(BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()