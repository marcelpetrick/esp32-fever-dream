#include "record_codec.h"

namespace fever {
namespace {

bool IsValidStatus(uint8_t value) { return value <= static_cast<uint8_t>(ReadingStatus::kTimeUnknown); }

bool IsValidFlags(uint8_t value) {
    constexpr uint8_t kKnownFlags =
        static_cast<uint8_t>(ReadingFlags::kTimeEstimated) | static_cast<uint8_t>(ReadingFlags::kRecognitionRuleBased) |
        static_cast<uint8_t>(ReadingFlags::kRecognitionTinyMl) | static_cast<uint8_t>(ReadingFlags::kRecognitionHybrid);
    return (value & static_cast<uint8_t>(~kKnownFlags)) == 0U;
}

void PutU16(std::array<uint8_t, RecordCodec::kEncodedSize>& out, std::size_t offset, uint16_t value) {
    out[offset] = static_cast<uint8_t>(value & 0xFFU);
    out[offset + 1U] = static_cast<uint8_t>((value >> 8U) & 0xFFU);
}

void PutU32(std::array<uint8_t, RecordCodec::kEncodedSize>& out, std::size_t offset, uint32_t value) {
    out[offset] = static_cast<uint8_t>(value & 0xFFU);
    out[offset + 1U] = static_cast<uint8_t>((value >> 8U) & 0xFFU);
    out[offset + 2U] = static_cast<uint8_t>((value >> 16U) & 0xFFU);
    out[offset + 3U] = static_cast<uint8_t>((value >> 24U) & 0xFFU);
}

uint16_t GetU16(const std::array<uint8_t, RecordCodec::kEncodedSize>& in, std::size_t offset) {
    return static_cast<uint16_t>(in[offset]) | (static_cast<uint16_t>(in[offset + 1U]) << 8U);
}

uint32_t GetU32(const std::array<uint8_t, RecordCodec::kEncodedSize>& in, std::size_t offset) {
    return static_cast<uint32_t>(in[offset]) | (static_cast<uint32_t>(in[offset + 1U]) << 8U) |
           (static_cast<uint32_t>(in[offset + 2U]) << 16U) | (static_cast<uint32_t>(in[offset + 3U]) << 24U);
}

}  // namespace

std::array<uint8_t, RecordCodec::kEncodedSize> RecordCodec::Encode(const ReadingRecord& record) {
    std::array<uint8_t, kEncodedSize> out{};
    PutU32(out, 0U, record.timestamp_s);
    PutU16(out, 4U, static_cast<uint16_t>(record.temperature_centi_c));
    out[6] = static_cast<uint8_t>(record.status);
    out[7] = record.confidence.value;
    out[8] = static_cast<uint8_t>(record.flags);
    out[9] = record.humidity_percent;
    PutU16(out, 10U, record.recognition_duration_ms);
    PutU16(out, 12U, Checksum(out));
    return out;
}

std::optional<ReadingRecord> RecordCodec::Decode(const std::array<uint8_t, kEncodedSize>& encoded) {
    if (Checksum(encoded) != GetU16(encoded, 12U)) {
        return std::nullopt;
    }
    if (!IsValidStatus(encoded[6]) || encoded[7] > 100U || !IsValidFlags(encoded[8]) ||
        (encoded[9] > 100U && encoded[9] != kHumidityUnavailable)) {
        return std::nullopt;
    }

    return ReadingRecord{
        GetU32(encoded, 0U),
        static_cast<int16_t>(GetU16(encoded, 4U)),
        encoded[9],
        static_cast<ReadingStatus>(encoded[6]),
        ConfidencePercent{encoded[7]},
        GetU16(encoded, 10U),
        static_cast<ReadingFlags>(encoded[8]),
    };
}

uint16_t RecordCodec::Checksum(const std::array<uint8_t, kEncodedSize>& encoded) {
    uint16_t checksum = 0xA5A5U;
    for (std::size_t i = 0U; i < 12U; ++i) {
        checksum = static_cast<uint16_t>((checksum << 5U) | (checksum >> 11U));
        checksum = static_cast<uint16_t>(checksum ^ encoded[i]);
    }
    return checksum;
}

}  // namespace fever
