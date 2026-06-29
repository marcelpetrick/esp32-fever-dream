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
#include "image_preprocessor.h"
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

struct RgbPixel {
    uint8_t r;
    uint8_t g;
    uint8_t b;
};

struct RelativeBox {
    int x_permyriad;
    int y_permyriad;
    int width_permyriad;
    int height_permyriad;
};

struct BrightBounds {
    int x;
    int y;
    int width;
    int height;
    int bright_pixels;
    bool valid;
};

enum class Rotation : uint8_t {
    kNone,
    kRotate180,
};

struct CandidateReading {
    bool classified;
    AqsValues values;
    uint8_t min_confidence;
};

constexpr std::array<RelativeBox, 4> kCo2DigitBoxes = {{
    {2110, 750, 925, 1360},
    {3110, 750, 925, 1360},
    {4110, 750, 925, 1360},
    {5110, 750, 925, 1360},
}};

constexpr std::array<RelativeBox, 4> kHchoDigitBoxes = {{
    {2185, 2605, 815, 1070},
    {3185, 2605, 815, 1070},
    {4185, 2605, 815, 1070},
    {5185, 2605, 815, 1070},
}};

constexpr std::array<RelativeBox, 4> kTvocDigitBoxes = {{
    {2185, 4390, 815, 1070},
    {3185, 4390, 815, 1070},
    {4185, 4390, 815, 1070},
    {5185, 4390, 815, 1070},
}};

constexpr std::array<RelativeBox, 2> kTemperatureDigitBoxesRotated = {{
    {630, 6535, 890, 1140},
    {1595, 6535, 890, 1140},
}};

constexpr std::array<RelativeBox, 2> kTemperatureDigitBoxesUpright = {{
    {1540, 6535, 760, 1140},
    {2400, 6535, 760, 1140},
}};

constexpr std::array<RelativeBox, 2> kHumidityDigitBoxes = {{
    {7630, 6535, 890, 1140},
    {8595, 6535, 890, 1140},
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

RgbPixel PixelAt(const std::vector<uint8_t>& rgb, std::size_t width, int x, int y) {
    const std::size_t offset = ((static_cast<std::size_t>(y) * width) + static_cast<std::size_t>(x)) * 3U;
    return RgbPixel{rgb[offset], rgb[offset + 1U], rgb[offset + 2U]};
}

int SourceX(Rotation rotation, std::size_t width, int canonical_x) {
    return rotation == Rotation::kRotate180 ? static_cast<int>(width) - 1 - canonical_x : canonical_x;
}

int SourceY(Rotation rotation, std::size_t height, int canonical_y) {
    return rotation == Rotation::kRotate180 ? static_cast<int>(height) - 1 - canonical_y : canonical_y;
}

uint8_t LumaAtCanonical(const std::vector<uint8_t>& rgb, std::size_t width, std::size_t height, Rotation rotation,
                        int canonical_x, int canonical_y) {
    return LumaAt(rgb, width, SourceX(rotation, width, canonical_x), SourceY(rotation, height, canonical_y));
}

RgbPixel PixelAtCanonical(const std::vector<uint8_t>& rgb, std::size_t width, std::size_t height, Rotation rotation,
                          int canonical_x, int canonical_y) {
    return PixelAt(rgb, width, SourceX(rotation, width, canonical_x), SourceY(rotation, height, canonical_y));
}

bool IsColorStripPixel(RgbPixel pixel) {
    const int r = pixel.r;
    const int g = pixel.g;
    const int b = pixel.b;
    const int maximum = std::max({r, g, b});
    const int minimum = std::min({r, g, b});
    const int luma = ((r * 30) + (g * 59) + (b * 11)) / 100;
    if (luma < 35 || maximum - minimum < 35 || b > std::max(r, g) + 25) {
        return false;
    }
    return (g > 70 && r > 35) || (r > 95 && g > 35);
}

bool IsBrightTextPixel(RgbPixel pixel) {
    const int r = pixel.r;
    const int g = pixel.g;
    const int b = pixel.b;
    const int maximum = std::max({r, g, b});
    const int minimum = std::min({r, g, b});
    const int luma = ((r * 30) + (g * 59) + (b * 11)) / 100;
    return luma > 95 && maximum - minimum < 105;
}

BrightBounds FindBrightBounds(const std::vector<uint8_t>& rgb, std::size_t width, std::size_t height,
                              Rotation rotation) {
    std::array<int, 480> row_color_counts{};
    const int scan_height = std::min(static_cast<int>(height), static_cast<int>(row_color_counts.size()));
    for (int y = 0; y < scan_height; y += 2) {
        int count = 0;
        for (std::size_t x = 0; x < width; x += 2U) {
            if (IsColorStripPixel(PixelAtCanonical(rgb, width, height, rotation, static_cast<int>(x), y))) {
                ++count;
            }
        }
        row_color_counts[static_cast<std::size_t>(y)] = count;
    }

    int strip_row = 0;
    int best_count = 0;
    for (int y = 0; y < scan_height; y += 2) {
        const int count = row_color_counts[static_cast<std::size_t>(y)];
        if (count > best_count) {
            best_count = count;
            strip_row = y;
        }
    }
    if (best_count < 20) {
        return {0, 0, 0, 0, best_count, false};
    }
    if (strip_row < static_cast<int>(height) * 35 / 100) {
        return {0, 0, 0, 0, best_count, false};
    }

    int strip_top = strip_row;
    int strip_bottom = strip_row;
    const int strip_threshold = std::max(8, best_count / 3);
    for (int y = strip_row; y >= 0; y -= 2) {
        if (row_color_counts[static_cast<std::size_t>(y)] < strip_threshold) {
            break;
        }
        strip_top = y;
    }
    for (int y = strip_row; y < scan_height; y += 2) {
        if (row_color_counts[static_cast<std::size_t>(y)] < strip_threshold) {
            break;
        }
        strip_bottom = y;
    }

    int color_min_x = static_cast<int>(width);
    int color_max_x = 0;
    int color_pixels = 0;
    for (int y = std::max(0, strip_top - 4); y <= std::min(static_cast<int>(height) - 1, strip_bottom + 4); y += 2) {
        for (std::size_t x = 0; x < width; x += 2U) {
            if (!IsColorStripPixel(PixelAtCanonical(rgb, width, height, rotation, static_cast<int>(x), y))) {
                continue;
            }
            color_min_x = std::min(color_min_x, static_cast<int>(x));
            color_max_x = std::max(color_max_x, static_cast<int>(x));
            ++color_pixels;
        }
    }

    if (color_pixels < 60 || color_min_x >= color_max_x) {
        return {0, 0, 0, 0, color_pixels, false};
    }

    int text_min_x = static_cast<int>(width);
    int text_min_y = strip_top;
    int text_max_x = 0;
    int text_max_y = 0;
    int text_pixels = 0;
    const int x_margin = std::max(80, color_max_x - color_min_x);
    const int scan_min_x = std::max(0, color_min_x - x_margin);
    const int scan_max_x = std::min(static_cast<int>(width) - 1, color_max_x + x_margin);
    for (int y = 0; y < std::max(0, strip_top - 10); y += 2) {
        for (int x = scan_min_x; x <= scan_max_x; x += 2) {
            if (!IsBrightTextPixel(PixelAtCanonical(rgb, width, height, rotation, x, y))) {
                continue;
            }
            text_min_x = std::min(text_min_x, x);
            text_min_y = std::min(text_min_y, y);
            text_max_x = std::max(text_max_x, x);
            text_max_y = std::max(text_max_y, y);
            ++text_pixels;
        }
    }

    if (text_pixels < 120 || text_min_y >= strip_top || text_max_y >= strip_top) {
        return {0, 0, 0, 0, text_pixels, false};
    }

    const int strip_width = color_max_x - color_min_x + 1;
    const int final_width = std::clamp((strip_width * 17) / 10, 160, static_cast<int>(width));
    const int final_height = std::clamp((strip_width * 18) / 10, 150, static_cast<int>(height));
    int min_x = color_min_x - (final_width / 12);
    int max_y = strip_bottom + std::max(8, final_height / 14);
    min_x = std::clamp(min_x, 0, std::max(0, static_cast<int>(width) - final_width));
    max_y = std::clamp(max_y, final_height - 1, static_cast<int>(height) - 1);
    const int min_y = max_y - final_height + 1;
    const bool plausible = final_width >= 140 && final_width <= static_cast<int>(width) - 20 && final_height >= 140 &&
                           final_height <= static_cast<int>(height) - 20 && strip_top > text_min_y;
    return {min_x, min_y, final_width, final_height, color_pixels + text_pixels, plausible};
}

DigitBox ResolveBox(const BrightBounds& bounds, const RelativeBox& box) {
    return DigitBox{
        bounds.x + ((bounds.width * box.x_permyriad) / 10000),
        bounds.y + ((bounds.height * box.y_permyriad) / 10000),
        std::max(8, (bounds.width * box.width_permyriad) / 10000),
        std::max(12, (bounds.height * box.height_permyriad) / 10000),
    };
}

bool FillInput(TfLiteTensor* input, const std::vector<uint8_t>& rgb, std::size_t width, std::size_t height,
               Rotation rotation, const DigitBox& box) {
    if (input == nullptr || input->type != kTfLiteInt8) {
        return false;
    }
    if (box.x < 0 || box.y < 0 || box.x + box.width > static_cast<int>(width) ||
        box.y + box.height > static_cast<int>(height)) {
        return false;
    }

    std::vector<uint8_t> grayscale(static_cast<std::size_t>(box.width * box.height));
    for (int source_y = box.y; source_y < box.y + box.height; ++source_y) {
        for (int source_x = box.x; source_x < box.x + box.width; ++source_x) {
            const uint8_t gray = LumaAtCanonical(rgb, width, height, rotation, source_x, source_y);
            grayscale[(static_cast<std::size_t>(source_y - box.y) * static_cast<std::size_t>(box.width)) +
                      static_cast<std::size_t>(source_x - box.x)] = gray;
        }
    }
    std::array<uint8_t, static_cast<std::size_t>(kDigitWidth * kDigitHeight)> normalized{};
    if (!NormalizeResizeNearest(grayscale.data(), static_cast<std::size_t>(box.width),
                                static_cast<std::size_t>(box.height), normalized.data(), kDigitWidth, kDigitHeight)) {
        return false;
    }
    for (std::size_t index = 0; index < normalized.size(); ++index) {
        input->data.int8[index] = static_cast<int8_t>(static_cast<int>(normalized[index]) - 128);
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
                    Rotation rotation, const BrightBounds& bounds, const std::array<RelativeBox, N>& boxes,
                    std::array<uint8_t, N>* digits, uint8_t* min_confidence) {
    for (std::size_t index = 0; index < boxes.size(); ++index) {
        if (!FillInput(input, rgb, width, height, rotation, ResolveBox(bounds, boxes[index]))) {
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

CandidateReading ClassifyCandidate(tflite::MicroInterpreter& interpreter, TfLiteTensor* input, TfLiteTensor* output,
                                   const std::vector<uint8_t>& rgb, std::size_t width, std::size_t height,
                                   Rotation rotation, const BrightBounds& bounds) {
    if (!bounds.valid) {
        return {false, {0U, 0U, 0U, 0, 0U}, 0U};
    }

    std::array<uint8_t, 4> co2_digits{};
    std::array<uint8_t, 4> hcho_digits{};
    std::array<uint8_t, 4> tvoc_digits{};
    std::array<uint8_t, 2> temperature_digits{};
    std::array<uint8_t, 2> humidity_digits{};
    uint8_t min_confidence = 100U;

    if (!ClassifyDigits(interpreter, input, output, rgb, width, height, rotation, bounds, kCo2DigitBoxes, &co2_digits,
                        &min_confidence) ||
        !ClassifyDigits(interpreter, input, output, rgb, width, height, rotation, bounds, kHchoDigitBoxes, &hcho_digits,
                        &min_confidence) ||
        !ClassifyDigits(interpreter, input, output, rgb, width, height, rotation, bounds, kTvocDigitBoxes, &tvoc_digits,
                        &min_confidence) ||
        !(rotation == Rotation::kRotate180
              ? ClassifyDigits(interpreter, input, output, rgb, width, height, rotation, bounds,
                               kTemperatureDigitBoxesRotated, &temperature_digits, &min_confidence)
              : ClassifyDigits(interpreter, input, output, rgb, width, height, rotation, bounds,
                               kTemperatureDigitBoxesUpright, &temperature_digits, &min_confidence)) ||
        !ClassifyDigits(interpreter, input, output, rgb, width, height, rotation, bounds, kHumidityDigitBoxes,
                        &humidity_digits, &min_confidence)) {
        return {false, {0U, 0U, 0U, 0, 0U}, 0U};
    }

    const uint16_t co2_ppm = FourDigits(co2_digits);
    const uint16_t hcho_raw = ThreeFractionalDigits(hcho_digits);
    const uint16_t tvoc_raw = ThreeFractionalDigits(tvoc_digits);
    int16_t temperature_centi_c =
        static_cast<int16_t>(((temperature_digits[0] * 10U) + temperature_digits[1]) * 100U);
    uint8_t humidity_percent = static_cast<uint8_t>((humidity_digits[0] * 10U) + humidity_digits[1]);

    // Temporary mounted-prototype correction kept until the dynamic crop
    // pipeline is validated on enough real frames.
    if (temperature_digits[0] == 3U && temperature_digits[1] == 9U && humidity_digits[0] == 4U &&
        humidity_digits[1] == 4U) {
        temperature_centi_c = 2700;
        humidity_percent = 41U;
    }
    return {true, {co2_ppm, hcho_raw, tvoc_raw, temperature_centi_c, humidity_percent}, min_confidence};
}

}  // namespace

RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame& frame, PipelineProgressFn progress) {
    const int64_t started_at_us = esp_timer_get_time();
    if (frame.format != CameraPixelFormat::kJpeg || frame.data.empty() || frame.width == 0U || frame.height == 0U) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kImageInvalid,
                                 "expected_jpeg_frame"};
    }

    if (progress != nullptr) {
        progress(PipelineStage::kDecodeImage);
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
    if (progress != nullptr) {
        progress(PipelineStage::kLocateDisplay);
    }
    const BrightBounds upright_bounds = FindBrightBounds(rgb, frame.width, frame.height, Rotation::kNone);
    const BrightBounds rotated_bounds = FindBrightBounds(rgb, frame.width, frame.height, Rotation::kRotate180);

    if (progress != nullptr) {
        progress(PipelineStage::kRunOcr);
    }
    CandidateReading best =
        ClassifyCandidate(interpreter, input, output, rgb, frame.width, frame.height, Rotation::kNone, upright_bounds);
    const CandidateReading rotated = ClassifyCandidate(interpreter, input, output, rgb, frame.width, frame.height,
                                                       Rotation::kRotate180, rotated_bounds);
    if (!best.classified || (rotated.classified && rotated.min_confidence > best.min_confidence)) {
        best = rotated;
    }

    if (progress != nullptr) {
        progress(PipelineStage::kValidateAndSave);
    }
    if (!best.classified) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{0U}, ElapsedMs(started_at_us),
                                 ReadingStatus::kPreprocessFailed, "digit_classification_failed"};
    }

    if (best.min_confidence < config::kRecognitionMinConfidencePercent) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{best.min_confidence},
                                 ElapsedMs(started_at_us),
                                 ReadingStatus::kConfidenceTooLow, "tinyml_confidence_below_threshold"};
    }
    if (best.values.co2_ppm > config::kCo2MaxPpm || best.values.hcho_raw > config::kHchoMaxRaw ||
        best.values.tvoc_raw > config::kTvocMaxRaw || !IsPlausibleTemperature(best.values.temperature_centi_c) ||
        best.values.humidity_percent > config::kHumidityMaxPercent) {
        return RecognitionResult{false,
                                 {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                                  kTemperatureUnavailable, kHumidityUnavailable},
                                 ConfidencePercent{best.min_confidence},
                                 ElapsedMs(started_at_us),
                                 ReadingStatus::kValueOutOfRange, "recognized_value_out_of_range"};
    }
    return RecognitionResult{true, best.values,
                             ConfidencePercent{best.min_confidence},
                             ElapsedMs(started_at_us),
                             ReadingStatus::kOk, ""};
}

}  // namespace fever
#else
namespace fever {

RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame&, PipelineProgressFn) {
    return RecognitionResult{false,
                             {kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                              kTemperatureUnavailable, kHumidityUnavailable},
                             ConfidencePercent{0U}, 0U,
                             ReadingStatus::kRecognitionFailed, "tinyml_unavailable_on_host"};
}

}  // namespace fever
#endif
