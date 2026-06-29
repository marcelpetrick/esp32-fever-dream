#pragma once

#include <cstddef>
#include <cstdint>

namespace fever::config {

inline constexpr uint32_t kMeasurementIntervalSeconds = 10U;
inline constexpr std::size_t kDefaultStorageRecords = 100000U;
inline constexpr std::size_t kRuntimeStorageRecords = kDefaultStorageRecords;
inline constexpr uint16_t kCo2MaxPpm = 9999U;
inline constexpr uint16_t kHchoMaxRaw = 9999U;
inline constexpr uint16_t kTvocMaxRaw = 9999U;
inline constexpr int16_t kTemperatureMinCentiC = -2000;
inline constexpr int16_t kTemperatureMaxCentiC = 6000;
inline constexpr uint8_t kHumidityMaxPercent = 100U;
inline constexpr uint8_t kRecognitionMinConfidencePercent = 67U;

// Flash persistence: save the last N records to NVS every M measurement cycles.
// At 10 s per cycle, kPersistenceIntervalCycles = 360 means one save per hour
// (~24 NVS page erases per day, well within flash endurance).
inline constexpr std::size_t kPersistenceRecords = 300U;
inline constexpr uint32_t kPersistenceIntervalCycles = 360U;

inline constexpr uint16_t kRoiX = 40U;
inline constexpr uint16_t kRoiY = 80U;
inline constexpr uint16_t kRoiWidth = 240U;
inline constexpr uint16_t kRoiHeight = 80U;

namespace ai_thinker {
inline constexpr int kPinPwdn = 32;
inline constexpr int kPinReset = -1;
inline constexpr int kPinXclk = 0;
inline constexpr int kPinSiod = 26;
inline constexpr int kPinSioc = 27;
inline constexpr int kPinD7 = 35;
inline constexpr int kPinD6 = 34;
inline constexpr int kPinD5 = 39;
inline constexpr int kPinD4 = 36;
inline constexpr int kPinD3 = 21;
inline constexpr int kPinD2 = 19;
inline constexpr int kPinD1 = 18;
inline constexpr int kPinD0 = 5;
inline constexpr int kPinVsync = 25;
inline constexpr int kPinHref = 23;
inline constexpr int kPinPclk = 22;
}  // namespace ai_thinker

}  // namespace fever::config
