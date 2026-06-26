#include "record_codec.h"

#include "app_config.h"

namespace fever {
namespace {

bool IsValidStatus(uint8_t value) { return value <= static_cast<uint8_t>(ReadingStatus::kTimeUnknown); }

bool IsValidFlags(uint8_t value) {
    constexpr uint8_t kKnownFlags =
        static_cast<uint8_t>(ReadingFlags::kTimeEstimated) | static_cast<uint8_t>(ReadingFlags::kRecognitionRuleBased) |
        static_cast<uint8_t>(ReadingFlags::kRecognitionTinyMl) | static_cast<uint8_t>(ReadingFlags::kRecognitionHybrid);
    return (value & static_cast<uint8_t>(~kKnownFlags)) == 0U;
}

bool IsValidAqsValues(uint16_t co2_ppm, uint16_t hcho_raw, uint16_t tvoc_raw, uint8_t humidity_percent) {
    return (co2_ppm <= config::kCo2MaxPpm || co2_ppm == kAqsUnsignedUnavailable) &&
           (hcho_raw <= config::kHchoMaxRaw || hcho_raw == kAqsUnsignedUnavailable) &&
           (tvoc_raw <= config::kTvocMaxRaw || tvoc_raw == kAqsUnsignedUnavailable) &&
           (humidity_percent <= config::kHumidityMaxPercent || humidity_percent == kHumidityUnavailable);
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
    out[0] = kSchemaVersion;
    out[1] = static_cast<uint8_t>(record.status);
    out[2] = static_cast<uint8_t>(record.flags);
    out[3] = record.confidence.value;
    PutU32(out, 4U, record.timestamp_s);
    PutU16(out, 8U, record.co2_ppm);
    PutU16(out, 10U, record.hcho_raw);
    PutU16(out, 12U, record.tvoc_raw);
    PutU16(out, 14U, static_cast<uint16_t>(record.temperature_centi_c));
    out[16] = record.humidity_percent;
    out[17] = 0U;
    PutU16(out, 18U, record.recognition_duration_ms);
    PutU16(out, 20U, Checksum(out));
    return out;
}

std::optional<ReadingRecord> RecordCodec::Decode(const std::array<uint8_t, kEncodedSize>& encoded) {
    if (encoded[0] != kSchemaVersion || Checksum(encoded) != GetU16(encoded, 20U)) {
        return std::nullopt;
    }
    if (!IsValidStatus(encoded[1]) || !IsValidFlags(encoded[2]) || encoded[3] > 100U ||
        !IsValidAqsValues(GetU16(encoded, 8U), GetU16(encoded, 10U), GetU16(encoded, 12U), encoded[16])) {
        return std::nullopt;
    }

    return ReadingRecord{
        GetU32(encoded, 4U),
        GetU16(encoded, 8U),
        GetU16(encoded, 10U),
        GetU16(encoded, 12U),
        static_cast<int16_t>(GetU16(encoded, 14U)),
        encoded[16],
        static_cast<ReadingStatus>(encoded[1]),
        ConfidencePercent{encoded[3]},
        GetU16(encoded, 18U),
        static_cast<ReadingFlags>(encoded[2]),
    };
}

uint16_t RecordCodec::Checksum(const std::array<uint8_t, kEncodedSize>& encoded) {
    uint16_t checksum = 0xA5A5U;
    for (std::size_t i = 0U; i < 20U; ++i) {
        checksum = static_cast<uint16_t>((checksum << 5U) | (checksum >> 11U));
        checksum = static_cast<uint16_t>(checksum ^ encoded[i]);
    }
    return checksum;
}

}  // namespace fever
