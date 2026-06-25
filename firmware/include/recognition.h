#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "reading_record.h"

namespace fever {

/** Seven-segment activation state for one segmented digit. */
struct DigitSegments {
    /** Top segment. */
    bool top;
    /** Upper-left segment. */
    bool upper_left;
    /** Upper-right segment. */
    bool upper_right;
    /** Middle segment. */
    bool middle;
    /** Lower-left segment. */
    bool lower_left;
    /** Lower-right segment. */
    bool lower_right;
    /** Bottom segment. */
    bool bottom;
};

/** Recognition result passed into validation, storage, and API layers. */
struct RecognitionResult {
    /** True when a plausible temperature was recognized. */
    bool ok;
    /** Temperature in centi-degrees Celsius when `ok` is true. */
    int16_t temperature_centi_c;
    /** Relative humidity percent, or kHumidityUnavailable when unknown. */
    uint8_t humidity_percent;
    /** Recognition confidence percentage. */
    ConfidencePercent confidence;
    /** End-to-end recognition runtime in milliseconds. */
    uint32_t recognition_duration_ms;
    /** Status code describing success or failure. */
    ReadingStatus status;
    /** Stable diagnostic reason for failed recognition. */
    std::string error;
};

/** Decode one seven-segment digit, returning empty for impossible segment masks. */
[[nodiscard]] std::optional<uint8_t> DecodeSevenSegmentDigit(const DigitSegments& segments);
/** Parse already-segmented display text into a validated temperature result. */
[[nodiscard]] RecognitionResult ParseDisplayText(const std::string& display_text, ConfidencePercent confidence);
/** Return true when a centi-Celsius value is within configured physical limits. */
[[nodiscard]] bool IsPlausibleTemperature(int16_t temperature_centi_c);

}  // namespace fever
