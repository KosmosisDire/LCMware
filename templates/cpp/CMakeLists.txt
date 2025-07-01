cmake_minimum_required(VERSION 3.10)

add_executable(project_name main.cpp)
target_link_libraries(project_name lcmware)
target_compile_features(project_name PRIVATE cxx_std_17)
target_compile_options(project_name PRIVATE -fpermissive)

install(TARGETS project_name RUNTIME DESTINATION bin/)