#include "recognition.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <climits>

#include "app_config.h"

namespace fever {

std::optional<uint8_t> DecodeSevenSegmentDigit(const DigitSegments& segments) {
    const std::array<bool, 7> mask = {segments.top,        segments.upper_left,  segments.upper_right, segments.middle,
                                      segments.lower_left, segments.lower_right, segments.bottom};
    constexpr std::array<std::array<bool, 7>, 10> digits = {{
        {true, true, true, false, true, true, true},
        {false, false, true, false, false, true, false},
        {true, false, true, true, true, false, true},
        {true, false, true, true, false, true, true},
        {false, true, true, true, false, true, false},
        {true, true, false, true, false, true, true},
        {true, true, false, true, true, true, true},
        {true, false, true, false, false, true, false},
        {true, true, true, true, true, true, true},
        {true, true, true, true, false, true, true},
    }};

    const auto match = std::find(digits.begin(), digits.end(), mask);
    if (match != digits.end()) {
        return static_cast<uint8_t>(std::distance(digits.begin(), match));
    }
    return std::nullopt;
}

RecognitionResult ParseDisplayText(const std::string& display_text, ConfidencePercent confidence) {
    if (display_text.empty()) {
        return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U, ReadingStatus::kRecognitionFailed,
                                 "empty_display_text"};
    }
    if (confidence.value < config::kRecognitionMinConfidencePercent) {
        return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U, ReadingStatus::kConfidenceTooLow,
                                 "confidence_below_threshold"};
    }

    int sign = 1;
    std::size_t index = 0U;
    if (display_text[index] == '-') {
        sign = -1;
        ++index;
    }

    int32_t whole = 0;
    int32_t fractional = 0;
    int32_t fractional_scale = 1;
    bool seen_digit = false;
    bool seen_decimal = false;

    for (; index < display_text.size(); ++index) {
        const char ch = display_text[index];
        if (ch == '.') {
            if (seen_decimal) {
                return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U,
                                         ReadingStatus::kRecognitionFailed,
                                         "duplicate_decimal"};
            }
            seen_decimal = true;
            continue;
        }
        if (!std::isdigit(static_cast<unsigned char>(ch))) {
            return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U,
                                     ReadingStatus::kRecognitionFailed,
                                     "invalid_character"};
        }
        seen_digit = true;
        const int32_t digit = ch - '0';
        if (seen_decimal) {
            if (fractional_scale >= 100) {
                return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U,
                                         ReadingStatus::kRecognitionFailed,
                                         "too_many_decimals"};
            }
            fractional = (fractional * 10) + digit;
            fractional_scale *= 10;
        } else {
            whole = (whole * 10) + digit;
        }
    }

    if (!seen_digit) {
        return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U, ReadingStatus::kRecognitionFailed,
                                 "no_digits"};
    }

    while (fractional_scale < 100) {
        fractional *= 10;
        fractional_scale *= 10;
    }

    const int32_t centi = sign * ((whole * 100) + fractional);
    if (centi < INT16_MIN || centi > INT16_MAX) {
        return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U, ReadingStatus::kValueOutOfRange,
                                 "value_overflows_record"};
    }
    if (!IsPlausibleTemperature(static_cast<int16_t>(centi))) {
        return RecognitionResult{false, 0, kHumidityUnavailable, confidence, 0U, ReadingStatus::kValueOutOfRange,
                                 "temperature_out_of_range"};
    }

    return RecognitionResult{true, static_cast<int16_t>(centi), kHumidityUnavailable, confidence, 0U,
                             ReadingStatus::kOk,
                             ""};
}

bool IsPlausibleTemperature(int16_t temperature_centi_c) {
    return temperature_centi_c >= config::kTemperatureMinCentiC && temperature_centi_c <= config::kTemperatureMaxCentiC;
}

}  // namespace fever
