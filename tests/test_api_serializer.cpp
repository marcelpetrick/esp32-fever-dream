#include "api_serializer.h"
#include "test_support.h"

void TestApiSerializer() {
    const auto record = fever::ReadingRecord::Success(123U, 2175, fever::ConfidencePercent{94U},
                                                      fever::ReadingFlags::kRecognitionRuleBased);
    const std::string current = fever::SerializeCurrent(record);
    REQUIRE(current.find("\"temperature_c\":21.75") != std::string::npos);
    REQUIRE(current.find("\"status\":\"ok\"") != std::string::npos);

    fever::DiagnosticsSnapshot diagnostics{};
    diagnostics.boot_count = 2U;
    diagnostics.time_synced = true;
    diagnostics.last_error = "none";
    const std::string status = fever::SerializeStatus(diagnostics, 1U, 10U, &record);
    REQUIRE(status.find("\"firmware_version\":\"0.0.0\"") != std::string::npos);
    REQUIRE(status.find("\"time_synced\":true") != std::string::npos);
}
