cmake_minimum_required(VERSION 3.20)

if(DEFINED ENV{IDF_PATH})
    include($ENV{IDF_PATH}/tools/cmake/project.cmake)
    project(esp32_fever_dream)
else()
    project(esp32_fever_dream_host LANGUAGES CXX)

    set(CMAKE_CXX_STANDARD 20)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
    set(CMAKE_CXX_EXTENSIONS OFF)
    set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

    file(READ "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" FEVER_DREAM_VERSION_RAW)
    string(STRIP "${FEVER_DREAM_VERSION_RAW}" FEVER_DREAM_VERSION)
    add_compile_definitions(FEVER_DREAM_VERSION="${FEVER_DREAM_VERSION}")

    add_subdirectory(firmware)
    add_subdirectory(tests)
endif()
