#pragma once

#include "camera_manager.h"
#include "recognition.h"

namespace fever {

/** Run the generated TFLite digit model over the fixed display layout. */
[[nodiscard]] RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame& frame);

}  // namespace fever
