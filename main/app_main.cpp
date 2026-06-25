#include "app_config.h"
#include "diagnostics.h"
#include "esp_log.h"
#include "storage_ring_buffer.h"
#include "version.h"

namespace {
constexpr const char* kTag = "fever_dream";
}

extern "C" void app_main(void) {
    fever::Diagnostics diagnostics;
    diagnostics.RecordBoot();

    ESP_LOGI(kTag, "ESP32 Fever Dream firmware %s", fever::version::ProjectVersion());
    ESP_LOGI(kTag, "measurement interval: %u seconds", fever::config::kMeasurementIntervalSeconds);
    ESP_LOGI(kTag, "target board: AI-Thinker ESP32-CAM / OV2640");

    fever::StorageRingBuffer readings(16);
    const fever::ReadingRecord boot_record = fever::ReadingRecord::Failure(
        0U, fever::ReadingStatus::kTimeUnknown, fever::ConfidencePercent{0U}, fever::ReadingFlags::kTimeEstimated);
    const bool stored = readings.Append(boot_record);
    ESP_LOGI(kTag, "boot diagnostic record stored: %s", stored ? "yes" : "no");
}
