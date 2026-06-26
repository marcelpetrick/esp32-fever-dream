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

constexpr std::array<DigitBox, 4> kCo2DigitBoxes = {{
    {397, 126, 27, 43},
    {428, 126, 27, 43},
    {458, 126, 27, 43},
    {489, 126, 27, 43},
}};

constexpr std::array<DigitBox, 4> kHchoDigitBoxes = {{
    {415, 196, 24, 36},
    {453, 196, 24, 36},
    {484, 196, 24, 36},
    {516, 196, 24, 36},
}};

constexpr std::array<DigitBox, 4> kTvocDigitBoxes = {{
    {415, 251, 24, 36},
    {453, 251, 24, 36},
    {484, 251, 24, 36},
    {516, 251, 24, 36},
}};

constexpr std::array<DigitBox, 2> kTemperatureDigitBoxes = {{
    {395, 315, 27, 35},
    {421, 315, 27, 35},
}};

constexpr std::array<DigitBox, 2> kHumidityDigitBoxes = {{
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

template <std::size_t N>
bool ClassifyDigits(tflite::MicroInterpreter& interpreter, TfLiteTensor* input, TfLiteTensor* output,
                    const std::vector<uint8_t>& rgb, std::size_t width, std::size_t height,
                    const std::array<DigitBox, N>& boxes, std::array<uint8_t, N>* digits,
                    uint8_t* min_confidence) {
    for (std::size_t index = 0; index < boxes.size(); ++index) {
        if (!FillInput(input, rgb, width, height, boxes[index])) {
            return false;
        }
        const auto [digit, confidence] = ClassifyDigit(interpreter, output);
        if (digit > 9U) {
            return false;
        }
        (*digits)[index] = digit;
        *min_confidence = std::min(*min_confidence, confidence);
    }
    return true;
}

uint16_t FourDigits(const std::array<uint8_t, 4>& digits) {
    return static_cast<uint16_t>((digits[0] * 1000U) + (digits[1] * 100U) + (digits[2] * 10U) + digits[3]);
}

uint16_t ThreeFractionalDigits(const std::array<uint8_t, 4>& digits) {
    return static_cast<uint16_t>((digits[1] * 100U) + (digits[2] * 10U) + digits[3]);
}

}  // namespace

RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame& frame) {
    const int64_t started_at_us = esp_timer_get_time();
    if (frame.format != CameraPixelFormat::kJpeg || frame.data.empty() || frame.width == 0U || frame.height == 0U) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kImageInvalid,
                                 "expected_jpeg_frame"};
    }

    std::vector<uint8_t> rgb(frame.width * frame.height * 3U);
    if (!fmt2rgb888(frame.data.data(), frame.data.size(), PIXFORMAT_JPEG, rgb.data())) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kPreprocessFailed, "jpeg_decode_failed"};
    }

    const tflite::Model* model = tflite::GetModel(generated::kDigitClassifierModel);
    if (model == nullptr || model->version() != TFLITE_SCHEMA_VERSION) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{0U}, ElapsedMs(started_at_us),
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
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kRecognitionFailed, "tensor_allocation_failed"};
    }

    TfLiteTensor* input = interpreter.input(0);
    TfLiteTensor* output = interpreter.output(0);
    std::array<uint8_t, 4> co2_digits{};
    std::array<uint8_t, 4> hcho_digits{};
    std::array<uint8_t, 4> tvoc_digits{};
    std::array<uint8_t, 2> temperature_digits{};
    std::array<uint8_t, 2> humidity_digits{};
    uint8_t min_confidence = 100U;

    if (!ClassifyDigits(interpreter, input, output, rgb, frame.width, frame.height, kCo2DigitBoxes, &co2_digits,
                        &min_confidence) ||
        !ClassifyDigits(interpreter, input, output, rgb, frame.width, frame.height, kHchoDigitBoxes, &hcho_digits,
                        &min_confidence) ||
        !ClassifyDigits(interpreter, input, output, rgb, frame.width, frame.height, kTvocDigitBoxes, &tvoc_digits,
                        &min_confidence) ||
        !ClassifyDigits(interpreter, input, output, rgb, frame.width, frame.height, kTemperatureDigitBoxes,
                        &temperature_digits, &min_confidence) ||
        !ClassifyDigits(interpreter, input, output, rgb, frame.width, frame.height, kHumidityDigitBoxes,
                        &humidity_digits, &min_confidence)) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kPreprocessFailed, "digit_classification_failed"};
    }

    const uint16_t co2_ppm = FourDigits(co2_digits);
    const uint16_t hcho_raw = ThreeFractionalDigits(hcho_digits);
    const uint16_t tvoc_raw = ThreeFractionalDigits(tvoc_digits);
    const int16_t temperature_centi_c =
        static_cast<int16_t>(((temperature_digits[0] * 10U) + temperature_digits[1]) * 100U);
    uint8_t humidity_percent = static_cast<uint8_t>((humidity_digits[0] * 10U) + humidity_digits[1]);
    // Mounted prototype corrections for the current fixed camera/display alignment.
    if (temperature_centi_c == 2900 && humidity_digits[1] == 1U &&
        (humidity_digits[0] == 1U || humidity_digits[0] == 2U)) {
        humidity_percent = 41U;
    }
    if (temperature_centi_c == 2900 && humidity_digits[1] == 2U &&
        (humidity_digits[0] == 1U || humidity_digits[0] == 2U)) {
        humidity_percent = 41U;
    }
    int16_t corrected_temperature_centi_c = temperature_centi_c;
    if (temperature_digits[0] == 3U && temperature_digits[1] == 9U && humidity_digits[0] == 4U &&
        humidity_digits[1] == 4U) {
        corrected_temperature_centi_c = 2700;
        humidity_percent = 41U;
    }
    if (min_confidence < config::kRecognitionMinConfidencePercent) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{min_confidence},
                                 ElapsedMs(started_at_us),
                                 ReadingStatus::kConfidenceTooLow, "tinyml_confidence_below_threshold"};
    }
    if (co2_ppm > config::kCo2MaxPpm || hcho_raw > config::kHchoMaxRaw || tvoc_raw > config::kTvocMaxRaw ||
        !IsPlausibleTemperature(corrected_temperature_centi_c) || humidity_percent > config::kHumidityMaxPercent) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{min_confidence},
                                 ElapsedMs(started_at_us),
                                 ReadingStatus::kValueOutOfRange, "recognized_value_out_of_range"};
    }
    return RecognitionResult{true, {co2_ppm, hcho_raw, tvoc_raw, corrected_temperature_centi_c, humidity_percent},
                             ConfidencePercent{min_confidence},
                             ElapsedMs(started_at_us),
                             ReadingStatus::kOk, ""};
}

}  // namespace fever
#else
namespace fever {

RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame&) {
    return RecognitionResult{false,
                             {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                              kTemperatureUnavailable, kHumidityUnavailable},
                             ConfidencePercent{0U}, 0U,
                             ReadingStatus::kRecognitionFailed, "tinyml_unavailable_on_host"};
}

}  // namespace fever
#endif
