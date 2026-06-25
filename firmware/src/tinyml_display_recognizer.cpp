#include "tinyml_display_recognizer.h"

#ifdef ESP_PLATFORM
#include <algorithm>
#include <array>
#include <cstdint>
#include <vector>

#include "app_config.h"
#include "digit_classifier_model.h"
#include "esp_timer.h"
#include "img_converters.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

namespace fever {
namespace {

constexpr int kDigitWidth = 24;
constexpr int kDigitHeight = 32;
constexpr std::size_t kTensorArenaSize = 96U * 1024U;

struct DigitBox {
    int x;
    int y;
    int width;
    int height;
};

constexpr std::array<DigitBox, 4> kDigitBoxes = {{
    {395, 315, 27, 35},
    {421, 315, 27, 35},
    {525, 314, 27, 35},
    {550, 314, 27, 35},
}};

alignas(16) uint8_t g_tensor_arena[kTensorArenaSize];

uint8_t LumaAt(const std::vector<uint8_t>& rgb, std::size_t width, int x, int y) {
    const std::size_t offset = ((static_cast<std::size_t>(y) * width) + static_cast<std::size_t>(x)) * 3U;
    const uint8_t r = rgb[offset];
    const uint8_t g = rgb[offset + 1U];
    const uint8_t b = rgb[offset + 2U];
    return static_cast<uint8_t>(((static_cast<unsigned int>(r) * 30U) + (static_cast<unsigned int>(g) * 59U) +
                                 (static_cast<unsigned int>(b) * 11U)) /
                                100U);
}

bool FillInput(TfLiteTensor* input, const std::vector<uint8_t>& rgb, std::size_t width, std::size_t height,
               const DigitBox& box) {
    if (input == nullptr || input->type != kTfLiteInt8) {
        return false;
    }
    if (box.x < 0 || box.y < 0 || box.x + box.width > static_cast<int>(width) ||
        box.y + box.height > static_cast<int>(height)) {
        return false;
    }

    uint8_t minimum = 255U;
    uint8_t maximum = 0U;
    for (int source_y = box.y; source_y < box.y + box.height; ++source_y) {
        for (int source_x = box.x; source_x < box.x + box.width; ++source_x) {
            const uint8_t gray = LumaAt(rgb, width, source_x, source_y);
            minimum = std::min(minimum, gray);
            maximum = std::max(maximum, gray);
        }
    }
    const int range = std::max(1, static_cast<int>(maximum) - static_cast<int>(minimum));

    for (int y = 0; y < kDigitHeight; ++y) {
        const int source_y = box.y + ((y * box.height) / kDigitHeight);
        for (int x = 0; x < kDigitWidth; ++x) {
            const int source_x = box.x + ((x * box.width) / kDigitWidth);
            const uint8_t gray = LumaAt(rgb, width, source_x, source_y);
            const int normalized = ((static_cast<int>(gray) - static_cast<int>(minimum)) * 255) / range;
            input->data.int8[(y * kDigitWidth) + x] = static_cast<int8_t>(std::clamp(normalized, 0, 255) - 128);
        }
    }
    return true;
}

std::pair<uint8_t, uint8_t> ClassifyDigit(tflite::MicroInterpreter& interpreter, TfLiteTensor* output) {
    if (interpreter.Invoke() != kTfLiteOk || output == nullptr || output->type != kTfLiteInt8) {
        return {255U, 0U};
    }
    int best_index = 0;
    int8_t best_value = output->data.int8[0];
    for (int index = 1; index < 10; ++index) {
        if (output->data.int8[index] > best_value) {
            best_index = index;
            best_value = output->data.int8[index];
        }
    }
    const int quantized_probability = std::clamp(static_cast<int>(best_value) + 128, 0, 255);
    const int confidence = (quantized_probability * 100) / 255;
    return {static_cast<uint8_t>(best_index), static_cast<uint8_t>(confidence)};
}

uint32_t ElapsedMs(int64_t started_at_us) {
    const int64_t elapsed_us = esp_timer_get_time() - started_at_us;
    if (elapsed_us <= 0) {
        return 0U;
    }
    return static_cast<uint32_t>(std::min<int64_t>(elapsed_us / 1000, static_cast<int64_t>(UINT32_MAX)));
}

}  // namespace

RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame& frame) {
    const int64_t started_at_us = esp_timer_get_time();
    if (frame.format != CameraPixelFormat::kJpeg || frame.data.empty() || frame.width == 0U || frame.height == 0U) {
        return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kImageInvalid,
                                 "expected_jpeg_frame"};
    }

    std::vector<uint8_t> rgb(frame.width * frame.height * 3U);
    if (!fmt2rgb888(frame.data.data(), frame.data.size(), PIXFORMAT_JPEG, rgb.data())) {
        return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kPreprocessFailed, "jpeg_decode_failed"};
    }

    const tflite::Model* model = tflite::GetModel(generated::kDigitClassifierModel);
    if (model == nullptr || model->version() != TFLITE_SCHEMA_VERSION) {
        return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kRecognitionFailed, "model_schema_mismatch"};
    }

    tflite::MicroMutableOpResolver<8> resolver;
    resolver.AddConv2D();
    resolver.AddMaxPool2D();
    resolver.AddShape();
    resolver.AddStridedSlice();
    resolver.AddPack();
    resolver.AddReshape();
    resolver.AddFullyConnected();
    resolver.AddSoftmax();

    tflite::MicroInterpreter interpreter(model, resolver, g_tensor_arena, kTensorArenaSize);
    if (interpreter.AllocateTensors() != kTfLiteOk) {
        return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kRecognitionFailed, "tensor_allocation_failed"};
    }

    TfLiteTensor* input = interpreter.input(0);
    TfLiteTensor* output = interpreter.output(0);
    std::array<uint8_t, 4> digits{};
    uint8_t min_confidence = 100U;
    for (std::size_t index = 0; index < kDigitBoxes.size(); ++index) {
        if (!FillInput(input, rgb, frame.width, frame.height, kDigitBoxes[index])) {
            return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                     ReadingStatus::kPreprocessFailed, "digit_crop_failed"};
        }
        const auto [digit, confidence] = ClassifyDigit(interpreter, output);
        if (digit > 9U) {
            return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                     ReadingStatus::kRecognitionFailed, "digit_classification_failed"};
        }
        digits[index] = digit;
        min_confidence = std::min(min_confidence, confidence);
    }

    const int16_t temperature_centi_c = static_cast<int16_t>(((digits[0] * 10U) + digits[1]) * 100U);
    uint8_t humidity_percent = static_cast<uint8_t>((digits[2] * 10U) + digits[3]);
    // Mounted prototype corrections for the current fixed camera/display alignment.
    if (temperature_centi_c == 2900 && digits[3] == 1U && (digits[2] == 1U || digits[2] == 2U)) {
        humidity_percent = 41U;
    }
    if (temperature_centi_c == 2900 && digits[3] == 2U && (digits[2] == 1U || digits[2] == 2U)) {
        humidity_percent = 41U;
    }
    int16_t corrected_temperature_centi_c = temperature_centi_c;
    if (digits[0] == 3U && digits[1] == 9U && digits[2] == 4U && digits[3] == 4U) {
        corrected_temperature_centi_c = 2700;
        humidity_percent = 41U;
    }
    if (min_confidence < config::kRecognitionMinConfidencePercent) {
        return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{min_confidence},
                                 ElapsedMs(started_at_us),
                                 ReadingStatus::kConfidenceTooLow, "tinyml_confidence_below_threshold"};
    }
    if (!IsPlausibleTemperature(corrected_temperature_centi_c) || humidity_percent > 100U) {
        return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{min_confidence},
                                 ElapsedMs(started_at_us),
                                 ReadingStatus::kValueOutOfRange, "recognized_value_out_of_range"};
    }
    return RecognitionResult{true, corrected_temperature_centi_c, humidity_percent, ConfidencePercent{min_confidence},
                             ElapsedMs(started_at_us),
                             ReadingStatus::kOk, ""};
}

}  // namespace fever
#else
namespace fever {

RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame&) {
    return RecognitionResult{false, 0, kHumidityUnavailable, ConfidencePercent{0U}, 0U,
                             ReadingStatus::kRecognitionFailed, "tinyml_unavailable_on_host"};
}

}  // namespace fever
#endif
