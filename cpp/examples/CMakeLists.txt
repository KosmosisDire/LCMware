cmake_minimum_required(VERSION 3.10)

# Service demo executable
add_executable(service_demo service_demo.cpp)
target_link_libraries(service_demo lcmware)
target_compile_features(service_demo PRIVATE cxx_std_17)
target_compile_options(service_demo PRIVATE -fpermissive)

# Action demo executable
add_executable(action_demo action_demo.cpp)
target_link_libraries(action_demo lcmware)
target_compile_features(action_demo PRIVATE cxx_std_17)
target_compile_options(action_demo PRIVATE -fpermissive)

# Topic demo executable
add_executable(topic_demo topic_demo.cpp)
target_link_libraries(topic_demo lcmware)
target_compile_features(topic_demo PRIVATE cxx_std_17)
target_compile_options(topic_demo PRIVATE -fpermissive)

# Install examples
install(TARGETS service_demo action_demo topic_demo
    RUNTIME DESTINATION bin/lcmware_examples
)