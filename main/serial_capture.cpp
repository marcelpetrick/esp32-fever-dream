#include "serial_capture.h"

#include <array>
#include <cstdio>
#include <cstring>
#include <string_view>

#include "driver/uart.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"

namespace fever {
namespace {

constexpr const char* kTag = "serial_capture";
constexpr const char* kCaptureCommand = "CAPTURE_JPEG";
constexpr uart_port_t kConsoleUart = UART_NUM_0;
constexpr std::size_t kLineBufferSize = 160U;
constexpr std::size_t kRawChunkSize = 144U;
constexpr std::size_t kBase64ChunkSize = ((kRawChunkSize + 2U) / 3U) * 4U + 1U;

CameraManager* g_camera = nullptr;

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

void HandleCaptureCommand(std::string_view) {
    if (g_camera == nullptr) {
        printf("FEVER_CAPTURE_ERROR reason=camera_not_registered\n");
        return;
    }

    const CameraCaptureResult result = g_camera->LatestFrame();
    if (!result.ok || result.frame.format != CameraPixelFormat::kJpeg) {
        printf("FEVER_CAPTURE_ERROR reason=%s\n", result.error.empty() ? "capture_failed" : result.error.c_str());
        return;
    }

    esp_log_level_set("*", ESP_LOG_NONE);
    printf("FEVER_JPEG_BEGIN bytes=%u width=%u height=%u format=jpeg encoding=base64\n",
           static_cast<unsigned int>(result.frame.data.size()), static_cast<unsigned int>(result.frame.width),
           static_cast<unsigned int>(result.frame.height));
    WriteBase64Frame(result.frame);
    printf("FEVER_JPEG_END\n");
    fflush(stdout);
    esp_log_level_set("*", ESP_LOG_INFO);
}

void EnsureUartRxDriver() {
    uart_config_t config = {};
    config.baud_rate = 115200;
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.rx_flow_ctrl_thresh = 0;
    config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK_WITHOUT_ABORT(uart_param_config(kConsoleUart, &config));
    const esp_err_t result = uart_driver_install(kConsoleUart, 2048, 0, 0, nullptr, 0);
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) {
        ESP_LOGW(kTag, "uart driver install failed: %s", esp_err_to_name(result));
    }
}

void SerialCaptureTask(void*) {
    EnsureUartRxDriver();
    ESP_LOGI(kTag, "serial cached capture ready; send %s", kCaptureCommand);
    printf("FEVER_SERIAL_CAPTURE_READY command=%s\n", kCaptureCommand);
    fflush(stdout);

    std::array<char, kLineBufferSize> line = {};
    std::size_t line_length = 0U;
    std::array<uint8_t, 64> read_buffer = {};
    while (true) {
        const int bytes_read =
            uart_read_bytes(kConsoleUart, read_buffer.data(), read_buffer.size(), pdMS_TO_TICKS(100));
        if (bytes_read <= 0) {
            continue;
        }

        for (int index = 0; index < bytes_read; ++index) {
            const char byte = static_cast<char>(read_buffer[static_cast<std::size_t>(index)]);
            if (byte == '\r') {
                continue;
            }
            if (byte != '\n') {
                if (line_length + 1U < line.size()) {
                    line[line_length] = byte;
                    ++line_length;
                }
                continue;
            }

            line[line_length] = '\0';
            const std::string_view command(line.data(), line_length);
            if (command.substr(0U, std::strlen(kCaptureCommand)) == kCaptureCommand) {
                HandleCaptureCommand(command);
            } else if (!command.empty()) {
                printf("FEVER_CAPTURE_ERROR reason=unknown_command expected=%s\n", kCaptureCommand);
                fflush(stdout);
            }
            line_length = 0U;
        }
    }
}

}  // namespace

void StartSerialCaptureTask(CameraManager& camera) {
    g_camera = &camera;
    xTaskCreate(&SerialCaptureTask, "serial_capture", 8192, nullptr, 4, nullptr);
}

}  // namespace fever
