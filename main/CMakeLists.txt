file(READ "${CMAKE_CURRENT_LIST_DIR}/../VERSION" FEVER_DREAM_VERSION_RAW)
string(STRIP "${FEVER_DREAM_VERSION_RAW}" FEVER_DREAM_VERSION)

idf_component_register(
    SRCS
        "app_main.cpp"
        "debug_capture_server.cpp"
        "serial_capture.cpp"
        "../firmware/src/api_serializer.cpp"
        "../firmware/src/api_router.cpp"
        "../firmware/src/camera_manager.cpp"
        "../firmware/src/diagnostics.cpp"
        "../firmware/src/image_preprocessor.cpp"
        "../firmware/src/measurement_controller.cpp"
        "../firmware/src/measurement_scheduler.cpp"
        "../firmware/src/record_codec.cpp"
        "../firmware/src/reading_record.cpp"
        "../firmware/src/recognition.cpp"
        "../firmware/src/storage_ring_buffer.cpp"
        "../firmware/src/tinyml_display_recognizer.cpp"
        "../firmware/src/time_manager.cpp"
        "../firmware/src/version.cpp"
    INCLUDE_DIRS
        "../firmware/include"
        "../firmware/generated"
    REQUIRES
        esp_timer
        esp_http_server
        esp_event
        esp_netif
        esp_wifi
        mbedtls
        nvs_flash
        esp32-camera
        esp-tflite-micro
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE FEVER_DREAM_VERSION="${FEVER_DREAM_VERSION}")
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
