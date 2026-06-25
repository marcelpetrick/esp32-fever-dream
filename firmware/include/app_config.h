#pragma once

#include <cstddef>
#include <cstdint>

namespace fever::config {

inline constexpr uint32_t kMeasurementIntervalSeconds = 60U;
inline constexpr std::size_t kDefaultStorageRecords = 100000U;
inline constexpr int16_t kTemperatureMinCentiC = -2000;
inline constexpr int16_t kTemperatureMaxCentiC = 6000;
inline constexpr uint8_t kRecognitionMinConfidencePercent = 85U;

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
