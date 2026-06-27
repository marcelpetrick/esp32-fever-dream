#pragma once

#include "camera_manager.h"
#include "pipeline_stage.h"
#include "recognition.h"

namespace fever {

/** Run the generated TFLite digit model over the fixed display layout. */
using PipelineProgressFn = void (*)(PipelineStage);

[[nodiscard]] RecognitionResult RecognizeDisplayWithTinyMl(const CameraFrame& frame,
                                                           PipelineProgressFn progress = nullptr);

}  // namespace fever
