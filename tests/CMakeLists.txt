add_executable(fever_tests
    test_api_serializer.cpp
    test_image_preprocessor.cpp
    test_recognition.cpp
    test_storage_ring_buffer.cpp
    test_time_manager.cpp
    test_main.cpp
)

target_link_libraries(fever_tests PRIVATE fever_core)
target_compile_options(fever_tests PRIVATE -Wall -Wextra -Werror -pedantic)

add_custom_target(check COMMAND fever_tests DEPENDS fever_tests)
