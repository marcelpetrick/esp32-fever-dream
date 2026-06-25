#pragma once

#include "camera_manager.h"

namespace fever {

/** Start the local debug HTTP capture server for dataset collection. */
[[nodiscard]] bool StartDebugCaptureServer(CameraManager& camera);

}  // namespace fever
