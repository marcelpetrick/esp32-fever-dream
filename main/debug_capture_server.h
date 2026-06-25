#pragma once

#include "camera_manager.h"
#include "diagnostics.h"
#include "storage_ring_buffer.h"

namespace fever {

/** Start the local debug HTTP capture server for dataset collection. */
[[nodiscard]] bool StartDebugCaptureServer(CameraManager& camera, StorageRingBuffer& storage, Diagnostics& diagnostics);

}  // namespace fever
