#pragma once

#include <cstdint>

namespace fever {

/** Observable stage of one on-device measurement cycle. */
enum class PipelineStage : uint8_t {
    kWaiting = 0,
    kCaptureImage = 1,
    kDecodeImage = 2,
    kLocateDisplay = 3,
    kRunOcr = 4,
    kValidateAndSave = 5,
};

/** Stable API name for a measurement pipeline stage. */
[[nodiscard]] const char* ToString(PipelineStage stage);

}  // namespace fever
