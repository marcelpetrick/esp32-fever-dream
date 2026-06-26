#include "api_serializer.h"
#include "test_support.h"
#include "version.h"

void TestApiSerializer() {
    const auto record = fever::ReadingRecord::Success(123U, {728U, 57U, 159U, 2175, 44U},
                                                      fever::ConfidencePercent{94U},
                                                      fever::ReadingFlags::kRecognitionRuleBased);
    const std::string current = fever::SerializeCurrent(record);
    REQUIRE(current.find("\"co2_ppm\":728") != std::string::npos);
    REQUIRE(current.find("\"hcho\":0.057") != std::string::npos);
    REQUIRE(current.find("\"tvoc\":0.159") != std::string::npos);
    REQUIRE(current.find("\"temperature_c\":21.75") != std::string::npos);
    REQUIRE(current.find("\"humidity_percent\":44") != std::string::npos);
    REQUIRE(current.find("\"status\":\"ok\"") != std::string::npos);

    fever::DiagnosticsSnapshot diagnostics{};
    diagnostics.boot_count = 2U;
    diagnostics.time_synced = true;
    diagnostics.last_error = "none";
    const std::string status = fever::SerializeStatus(diagnostics, 1U, 10U, sizeof(record), sizeof(record) * 10U,
                                                      sizeof(record), &record);
    REQUIRE(status.find(std::string{"\"firmware_version\":\""} + fever::version::ProjectVersion() + "\"") !=
            std::string::npos);
    REQUIRE(status.find("\"time_synced\":true") != std::string::npos);
    REQUIRE(status.find("\"storage_backend\":\"ram_ring_buffer\"") != std::string::npos);
}
