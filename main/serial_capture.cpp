#include "serial_capture.h"

#include <algorithm>
#include <array>
#include <charconv>
#include <cstdio>
#include <cstring>
#include <string_view>

#include "esp_camera.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"

namespace fever {
namespace {

constexpr const char* kTag = "serial_capture";
constexpr const char* kCaptureCommand = "CAPTURE_JPEG";
constexpr std::size_t kLineBufferSize = 160U;
constexpr std::size_t kRawChunkSize = 144U;
constexpr std::size_t kBase64ChunkSize = ((kRawChunkSize + 2U) / 3U) * 4U + 1U;

CameraManager* g_camera = nullptr;

bool ParseInt(std::string_view raw_value, int* value) {
    int parsed = 0;
    const auto result = std::from_chars(raw_value.data(), raw_value.data() + raw_value.size(), parsed);
    if (raw_value.empty() || result.ec != std::errc{} || result.ptr != raw_value.data() + raw_value.size()) {
        return false;
    }
    *value = parsed;
    return true;
}

framesize_t ParseFrameSize(std::string_view value) {
    if (value == "qvga") {
        return FRAMESIZE_QVGA;
    }
    if (value == "vga") {
        return FRAMESIZE_VGA;
    }
    if (value == "svga") {
        return FRAMESIZE_SVGA;
    }
    return FRAMESIZE_VGA;
}

void ApplySetting(sensor_t* sensor, std::string_view key, std::string_view raw_value) {
    int value = 0;
    if (key == "framesize") {
        sensor->set_framesize(sensor, ParseFrameSize(raw_value));
        return;
    }
    if (!ParseInt(raw_value, &value)) {
        return;
    }
    if (key == "quality") {
        sensor->set_quality(sensor, std::clamp(value, 4, 63));
    } else if (key == "brightness") {
        sensor->set_brightness(sensor, std::clamp(value, -2, 2));
    } else if (key == "contrast") {
        sensor->set_contrast(sensor, std::clamp(value, -2, 2));
    } else if (key == "saturation") {
        sensor->set_saturation(sensor, std::clamp(value, -2, 2));
    } else if (key == "aec") {
        sensor->set_exposure_ctrl(sensor, value != 0 ? 1 : 0);
    } else if (key == "agc") {
        sensor->set_gain_ctrl(sensor, value != 0 ? 1 : 0);
    } else if (key == "awb") {
        sensor->set_whitebal(sensor, value != 0 ? 1 : 0);
    }
}

void ApplyCameraSettings(std::string_view command_line) {
    sensor_t* sensor = esp_camera_sensor_get();
    if (sensor == nullptr) {
        return;
    }

    std::size_t token_start = command_line.find(' ');
    while (token_start != std::string_view::npos) {
        while (token_start < command_line.size() && command_line[token_start] == ' ') {
            ++token_start;
        }
        if (token_start >= command_line.size()) {
            break;
        }

        const std::size_t token_end = command_line.find(' ', token_start);
        const std::string_view token =
            command_line.substr(token_start, (token_end == std::string_view::npos ? command_line.size() : token_end) -
                                                 token_start);
        const std::size_t equals = token.find('=');
        if (equals != std::string_view::npos) {
            ApplySetting(sensor, token.substr(0U, equals), token.substr(equals + 1U));
        }
        token_start = token_end;
    }
}

void WriteBase64Frame(const CameraFrame& frame) {
    std::array<unsigned char, kBase64ChunkSize> encoded = {};
    for (std::size_t offset = 0U; offset < frame.data.size(); offset += kRawChunkSize) {
        const std::size_t chunk_size = std::min(kRawChunkSize, frame.data.size() - offset);
        std::size_t encoded_size = 0U;
        const int result =
            mbedtls_base64_encode(encoded.data(), encoded.size(), &encoded_size, frame.data.data() + offset, chunk_size);
        if (result != 0) {
            printf("FEVER_CAPTURE_ERROR reason=base64_encode_failed code=%d\n", result);
            return;
        }
        fwrite(encoded.data(), 1U, encoded_size, stdout);
        putchar('\n');
    }
}

void HandleCaptureCommand(std::string_view command_line) {
    if (g_camera == nullptr) {
        printf("FEVER_CAPTURE_ERROR reason=camera_not_registered\n");
        return;
    }

    ApplyCameraSettings(command_line);
    const CameraCaptureResult result = g_camera->Capture();
    if (!result.ok || result.frame.format != CameraPixelFormat::kJpeg) {
        printf("FEVER_CAPTURE_ERROR reason=%s\n", result.error.empty() ? "capture_failed" : result.error.c_str());
        return;
    }

    printf("FEVER_JPEG_BEGIN bytes=%u width=%u height=%u format=jpeg encoding=base64\n",
           static_cast<unsigned int>(result.frame.data.size()), static_cast<unsigned int>(result.frame.width),
           static_cast<unsigned int>(result.frame.height));
    WriteBase64Frame(result.frame);
    printf("FEVER_JPEG_END\n");
    fflush(stdout);
}

void SerialCaptureTask(void*) {
    ESP_LOGI(kTag, "serial capture ready; send %s [framesize=vga] [quality=12]", kCaptureCommand);
    printf("FEVER_SERIAL_CAPTURE_READY command=%s\n", kCaptureCommand);
    fflush(stdout);

    std::array<char, kLineBufferSize> line = {};
    while (true) {
        if (fgets(line.data(), line.size(), stdin) == nullptr) {
            vTaskDelay(pdMS_TO_TICKS(100));
            clearerr(stdin);
            continue;
        }

        const std::size_t length = strcspn(line.data(), "\r\n");
        line[length] = '\0';
        const std::string_view command(line.data(), length);
        if (command.substr(0U, std::strlen(kCaptureCommand)) == kCaptureCommand) {
            HandleCaptureCommand(command);
        } else if (!command.empty()) {
            printf("FEVER_CAPTURE_ERROR reason=unknown_command expected=%s\n", kCaptureCommand);
            fflush(stdout);
        }
    }
}

}  // namespace

void StartSerialCaptureTask(CameraManager& camera) {
    g_camera = &camera;
    xTaskCreate(&SerialCaptureTask, "serial_capture", 8192, nullptr, 4, nullptr);
}

}  // namespace fever
