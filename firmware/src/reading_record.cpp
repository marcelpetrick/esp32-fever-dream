#include "reading_record.h"

namespace fever {

ReadingRecord ReadingRecord::Success(uint32_t timestamp_s, AqsValues values, ConfidencePercent confidence,
                                     ReadingFlags flags, uint16_t recognition_duration_ms) {
    return ReadingRecord{timestamp_s, values.co2_ppm, values.hcho_raw, values.tvoc_raw, values.temperature_centi_c,
                         values.humidity_percent, ReadingStatus::kOk, confidence, recognition_duration_ms, flags};
}

ReadingRecord ReadingRecord::Failure(uint32_t timestamp_s, ReadingStatus status, ConfidencePercent confidence,
                                     ReadingFlags flags, uint16_t recognition_duration_ms) {
    return ReadingRecord{timestamp_s, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable, kAqsUnsignedUnavailable,
                         kTemperatureUnavailable, kHumidityUnavailable, status, confidence, recognition_duration_ms,
                         flags};
}

bool ReadingRecord::IsSuccess() const { return status == ReadingStatus::kOk; }

std::optional<uint16_t> ReadingRecord::Co2Ppm() const {
    if (!IsSuccess() || co2_ppm == kAqsUnsignedUnavailable) {
        return std::nullopt;
    }
    return co2_ppm;
}

std::optional<uint16_t> ReadingRecord::HchoRaw() const {
    if (!IsSuccess() || hcho_raw == kAqsUnsignedUnavailable) {
        return std::nullopt;
    }
    return hcho_raw;
}

std::optional<uint16_t> ReadingRecord::TvocRaw() const {
    if (!IsSuccess() || tvoc_raw == kAqsUnsignedUnavailable) {
        return std::nullopt;
    }
    return tvoc_raw;
}

std::optional<float> ReadingRecord::TemperatureCelsius() const {
    if (!IsSuccess() || temperature_centi_c == kTemperatureUnavailable) {
        return std::nullopt;
    }
    return static_cast<float>(temperature_centi_c) / 100.0F;
}

std::optional<uint8_t> ReadingRecord::HumidityPercent() const {
    if (!IsSuccess() || humidity_percent == kHumidityUnavailable) {
        return std::nullopt;
    }
    return humidity_percent;
}

const char* ToString(ReadingStatus status) {
    switch (status) {
        case ReadingStatus::kOk:
            return "ok";
        case ReadingStatus::kCameraFailed:
            return "camera_failed";
        case ReadingStatus::kImageInvalid:
            return "image_invalid";
        case ReadingStatus::kPreprocessFailed:
            return "preprocess_failed";
        case ReadingStatus::kRecognitionFailed:
            return "recognition_failed";
        case ReadingStatus::kConfidenceTooLow:
            return "confidence_too_low";
        case ReadingStatus::kValueOutOfRange:
            return "value_out_of_range";
        case ReadingStatus::kStorageFailed:
            return "storage_failed";
        case ReadingStatus::kTimeUnknown:
            return "time_unknown";
    }
    return "unknown";
}

}  // namespace fever
