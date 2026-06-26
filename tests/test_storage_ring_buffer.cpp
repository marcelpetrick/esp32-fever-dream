#include "storage_ring_buffer.h"
#include "test_support.h"

void TestStorageRingBuffer() {
    fever::StorageRingBuffer buffer(3);
    REQUIRE(buffer.Empty());
    REQUIRE(buffer.Capacity() == 3U);

    REQUIRE(buffer.Append(fever::ReadingRecord::Success(10U, {700U, 40U, 100U, 2100, 41U}, fever::ConfidencePercent{95U},
                                                        fever::ReadingFlags::kRecognitionRuleBased)));
    REQUIRE(buffer.Append(fever::ReadingRecord::Success(20U, {710U, 41U, 101U, 2110, 42U}, fever::ConfidencePercent{96U},
                                                        fever::ReadingFlags::kRecognitionRuleBased)));
    REQUIRE(buffer.Count() == 2U);
    REQUIRE(buffer.Latest().has_value());
    REQUIRE(buffer.Latest()->timestamp_s == 20U);

    REQUIRE(buffer.Append(fever::ReadingRecord::Failure(30U, fever::ReadingStatus::kRecognitionFailed,
                                                        fever::ConfidencePercent{20U},
                                                        fever::ReadingFlags::kRecognitionRuleBased)));
    REQUIRE(buffer.Append(fever::ReadingRecord::Success(40U, {720U, 42U, 102U, 2120, 43U}, fever::ConfidencePercent{97U},
                                                        fever::ReadingFlags::kRecognitionRuleBased)));
    REQUIRE(buffer.Full());

    const auto readings = buffer.ReadChronological(10U);
    REQUIRE(readings.size() == 3U);
    REQUIRE(readings[0].timestamp_s == 20U);
    REQUIRE(readings[1].timestamp_s == 30U);
    REQUIRE(readings[2].timestamp_s == 40U);

    const auto limited = buffer.ReadChronological(2U);
    REQUIRE(limited.size() == 2U);
    REQUIRE(limited[0].timestamp_s == 30U);
    REQUIRE(limited[1].timestamp_s == 40U);
}
