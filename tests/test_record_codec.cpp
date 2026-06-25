#include "record_codec.h"
#include "test_support.h"

void TestRecordCodec() {
    const fever::ReadingRecord record =
        fever::ReadingRecord::Success(1750000000U, -125, fever::ConfidencePercent{98U},
                                      fever::ReadingFlags::kRecognitionRuleBased | fever::ReadingFlags::kTimeEstimated);

    const auto encoded = fever::RecordCodec::Encode(record);
    const auto decoded = fever::RecordCodec::Decode(encoded);
    REQUIRE(decoded.has_value());
    REQUIRE(decoded->timestamp_s == record.timestamp_s);
    REQUIRE(decoded->temperature_centi_c == record.temperature_centi_c);
    REQUIRE(decoded->humidity_percent == fever::kHumidityUnavailable);
    REQUIRE(decoded->status == record.status);
    REQUIRE(decoded->confidence.value == record.confidence.value);
    REQUIRE(fever::HasFlag(decoded->flags, fever::ReadingFlags::kRecognitionRuleBased));
    REQUIRE(fever::HasFlag(decoded->flags, fever::ReadingFlags::kTimeEstimated));

    auto corrupt = encoded;
    corrupt[0] ^= 0x01U;
    REQUIRE(!fever::RecordCodec::Decode(corrupt).has_value());

    const auto invalid_status = fever::RecordCodec::Encode(fever::ReadingRecord{
        record.timestamp_s,
        record.temperature_centi_c,
        fever::kHumidityUnavailable,
        static_cast<fever::ReadingStatus>(99U),
        record.confidence,
        record.flags,
    });
    REQUIRE(!fever::RecordCodec::Decode(invalid_status).has_value());

    REQUIRE(!fever::RecordCodec::Decode(fever::RecordCodec::Encode(fever::ReadingRecord{
                                            record.timestamp_s,
                                            record.temperature_centi_c,
                                            fever::kHumidityUnavailable,
                                            record.status,
                                            fever::ConfidencePercent{101U},
                                            record.flags,
                                        }))
                 .has_value());
}
