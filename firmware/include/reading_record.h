#pragma once

#include <cstdint>
#include <optional>

namespace fever {

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

/** Compact temperature reading or explicit failed measurement record. */
struct ReadingRecord {
    /** Unix timestamp in seconds, synchronized or estimated depending on flags. */
    uint32_t timestamp_s;
    /** Temperature in centi-degrees Celsius; valid only for successful records. */
    int16_t temperature_centi_c;
    /** Reading status. */
    ReadingStatus status;
    /** Recognition confidence percentage. */
    ConfidencePercent confidence;
    /** Metadata flags for this reading. */
    ReadingFlags flags;

    /** Construct a successful temperature reading. */
    static ReadingRecord Success(uint32_t timestamp_s, int16_t temperature_centi_c, ConfidencePercent confidence,
                                 ReadingFlags flags);
    /** Construct an explicit failed reading. */
    static ReadingRecord Failure(uint32_t timestamp_s, ReadingStatus status, ConfidencePercent confidence,
                                 ReadingFlags flags);

    /** Return true when this record contains a valid temperature. */
    [[nodiscard]] bool IsSuccess() const;
    /** Return the temperature in degrees Celsius when the record is successful. */
    [[nodiscard]] std::optional<float> TemperatureCelsius() const;
};

/** Convert a reading status to the stable API/storage string. */
[[nodiscard]] const char* ToString(ReadingStatus status);

}  // namespace fever
