#pragma once

#include <climits>
#include <cstdint>
#include <optional>

namespace fever {

inline constexpr uint8_t kHumidityUnavailable = 255U;
inline constexpr uint16_t kAqsUnsignedUnavailable = 65535U;
inline constexpr int16_t kTemperatureUnavailable = INT16_MIN;

/** Stable reading status codes exposed in storage and API responses. */
enum class ReadingStatus : uint8_t {
    kOk = 0,
    kCameraFailed = 1,
    kImageInvalid = 2,
    kPreprocessFailed = 3,
    kRecognitionFailed = 4,
    kConfidenceTooLow = 5,
    kValueOutOfRange = 6,
    kStorageFailed = 7,
    kTimeUnknown = 8,
};

/** Bit flags describing timestamp and recognition metadata. */
enum class ReadingFlags : uint8_t {
    kNone = 0,
    kTimeEstimated = 1U << 0U,
    kRecognitionRuleBased = 1U << 1U,
    kRecognitionTinyMl = 1U << 2U,
    kRecognitionHybrid = 1U << 3U,
};

/** Combine reading flags. */
constexpr ReadingFlags operator|(ReadingFlags left, ReadingFlags right) {
    return static_cast<ReadingFlags>(static_cast<uint8_t>(left) | static_cast<uint8_t>(right));
}

/** Return true when a flag is set. */
constexpr bool HasFlag(ReadingFlags flags, ReadingFlags flag) {
    return (static_cast<uint8_t>(flags) & static_cast<uint8_t>(flag)) != 0U;
}

/** Confidence represented as an integer percentage from 0 to 100. */
struct ConfidencePercent {
    /** Confidence percentage. */
    uint8_t value;
};

/** Five-value air quality sensor reading payload. */
struct AqsValues {
    /** Carbon dioxide concentration in parts per million. */
    uint16_t co2_ppm;
    /** HCHO display value, integer-scaled until the exact unit/decimal is confirmed. */
    uint16_t hcho_raw;
    /** TVOC display value, integer-scaled until the exact unit/decimal is confirmed. */
    uint16_t tvoc_raw;
    /** Temperature in centi-degrees Celsius. */
    int16_t temperature_centi_c;
    /** Relative humidity percent. */
    uint8_t humidity_percent;
};

/** Compact AQS reading or explicit failed measurement record. */
struct ReadingRecord {
    /** Unix timestamp in seconds, synchronized or estimated depending on flags. */
    uint32_t timestamp_s;
    /** CO2 concentration in ppm, or kAqsUnsignedUnavailable when unknown. */
    uint16_t co2_ppm;
    /** HCHO display value, or kAqsUnsignedUnavailable when unknown. */
    uint16_t hcho_raw;
    /** TVOC display value, or kAqsUnsignedUnavailable when unknown. */
    uint16_t tvoc_raw;
    /** Temperature in centi-degrees Celsius, or kTemperatureUnavailable when unknown. */
    int16_t temperature_centi_c;
    /** Relative humidity percent, or kHumidityUnavailable when unknown. */
    uint8_t humidity_percent;
    /** Reading status. */
    ReadingStatus status;
    /** Recognition confidence percentage. */
    ConfidencePercent confidence;
    /** End-to-end recognition runtime in milliseconds, capped for compact storage. */
    uint16_t recognition_duration_ms;
    /** Metadata flags for this reading. */
    ReadingFlags flags;

    /** Construct a successful AQS reading. */
    static ReadingRecord Success(uint32_t timestamp_s, AqsValues values, ConfidencePercent confidence,
                                 ReadingFlags flags, uint16_t recognition_duration_ms = 0U);
    /** Construct an explicit failed reading. */
    static ReadingRecord Failure(uint32_t timestamp_s, ReadingStatus status, ConfidencePercent confidence,
                                 ReadingFlags flags, uint16_t recognition_duration_ms = 0U);

    /** Return true when this record contains a valid temperature. */
    [[nodiscard]] bool IsSuccess() const;
    /** Return CO2 ppm when available. */
    [[nodiscard]] std::optional<uint16_t> Co2Ppm() const;
    /** Return HCHO display value when available. */
    [[nodiscard]] std::optional<uint16_t> HchoRaw() const;
    /** Return TVOC display value when available. */
    [[nodiscard]] std::optional<uint16_t> TvocRaw() const;
    /** Return the temperature in degrees Celsius when the record is successful. */
    [[nodiscard]] std::optional<float> TemperatureCelsius() const;
    /** Return humidity percent when available. */
    [[nodiscard]] std::optional<uint8_t> HumidityPercent() const;
};

/** Convert a reading status to the stable API/storage string. */
[[nodiscard]] const char* ToString(ReadingStatus status);

}  // namespace fever
