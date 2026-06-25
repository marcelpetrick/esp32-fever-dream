add_library(fever_core
    src/api_serializer.cpp
    src/api_router.cpp
    src/camera_manager.cpp
    src/diagnostics.cpp
    src/image_preprocessor.cpp
    src/measurement_controller.cpp
    src/record_codec.cpp
    src/reading_record.cpp
    src/recognition.cpp
    src/storage_ring_buffer.cpp
    src/time_manager.cpp
    src/version.cpp
)

target_include_directories(fever_core PUBLIC include)
target_compile_options(fever_core PRIVATE -Wall -Wextra -Werror -pedantic)
