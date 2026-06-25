#include "reading_record.h"

namespace fever {

ReadingRecord ReadingRecord::Success(uint32_t timestamp_s, int16_t temperature_centi_c, ConfidencePercent confidence,
                                     ReadingFlags flags, uint8_t humidity_percent) {
    return ReadingRecord{timestamp_s, temperature_centi_c, humidity_percent, ReadingStatus::kOk, confidence, flags};
}

ReadingRecord ReadingRecord::Failure(uint32_t timestamp_s, ReadingStatus status, ConfidencePercent confidence,
                                     ReadingFlags flags) {
    return ReadingRecord{timestamp_s, 0, kHumidityUnavailable, status, confidence, flags};
}

bool ReadingRecord::IsSuccess() const { return status == ReadingStatus::kOk; }

std::optional<float> ReadingRecord::TemperatureCelsius() const {
    if (!IsSuccess()) {
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
