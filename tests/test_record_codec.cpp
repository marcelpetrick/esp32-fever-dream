#include "record_codec.h"
#include "test_support.h"

void TestRecordCodec() {
    const fever::ReadingRecord record =
        fever::ReadingRecord::Success(1750000000U, {728U, 57U, 159U, -125, 44U}, fever::ConfidencePercent{98U},
                                      fever::ReadingFlags::kRecognitionRuleBased | fever::ReadingFlags::kTimeEstimated,
                                      1234U);

    const auto encoded = fever::RecordCodec::Encode(record);
    const auto decoded = fever::RecordCodec::Decode(encoded);
    REQUIRE(decoded.has_value());
    REQUIRE(decoded->timestamp_s == record.timestamp_s);
    REQUIRE(decoded->co2_ppm == record.co2_ppm);
    REQUIRE(decoded->hcho_raw == record.hcho_raw);
    REQUIRE(decoded->tvoc_raw == record.tvoc_raw);
    REQUIRE(decoded->temperature_centi_c == record.temperature_centi_c);
    REQUIRE(decoded->humidity_percent == record.humidity_percent);
    REQUIRE(decoded->status == record.status);
    REQUIRE(decoded->confidence.value == record.confidence.value);
    REQUIRE(decoded->recognition_duration_ms == record.recognition_duration_ms);
    REQUIRE(fever::HasFlag(decoded->flags, fever::ReadingFlags::kRecognitionRuleBased));
    REQUIRE(fever::HasFlag(decoded->flags, fever::ReadingFlags::kTimeEstimated));

    auto corrupt = encoded;
    corrupt[0] ^= 0x01U;
    REQUIRE(!fever::RecordCodec::Decode(corrupt).has_value());

    const auto invalid_status = fever::RecordCodec::Encode(fever::ReadingRecord{
        record.timestamp_s,
        record.co2_ppm,
        record.hcho_raw,
        record.tvoc_raw,
        record.temperature_centi_c,
        record.humidity_percent,
        static_cast<fever::ReadingStatus>(99U),
        record.confidence,
        record.recognition_duration_ms,
        record.flags,
    });
    REQUIRE(!fever::RecordCodec::Decode(invalid_status).has_value());

    REQUIRE(!fever::RecordCodec::Decode(fever::RecordCodec::Encode(fever::ReadingRecord{
                                            record.timestamp_s,
                                            record.co2_ppm,
                                            record.hcho_raw,
                                            record.tvoc_raw,
                                            record.temperature_centi_c,
                                            record.humidity_percent,
                                            record.status,
                                            fever::ConfidencePercent{101U},
                                            record.recognition_duration_ms,
                                            record.flags,
                                        }))
                 .has_value());
}
