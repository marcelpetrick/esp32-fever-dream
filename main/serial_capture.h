#pragma once

#include "camera_manager.h"

namespace fever {

/** Start the UART command task used as a no-Wi-Fi JPEG capture fallback. */
void StartSerialCaptureTask(CameraManager& camera);

}  // namespace fever
