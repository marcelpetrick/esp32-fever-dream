#pragma once

#include <functional>

#include "camera_manager.h"
#include "diagnostics.h"
#include "recognition.h"
#include "storage_ring_buffer.h"
#include "time_manager.h"

namespace fever {

/** Callable that captures one image frame. */
using CaptureFn = std::function<CameraCaptureResult()>;

/** Callable that recognizes one captured image frame. */
using RecognizeFn = std::function<RecognitionResult(const CameraFrame&)>;

/** Coordinates one capture-recognize-store measurement cycle. */
class MeasurementController {
   public:
    /** Create a controller over shared runtime state. */
    MeasurementController(StorageRingBuffer& storage, Diagnostics& diagnostics, TimeManager& time, CaptureFn capture,
                          RecognizeFn recognize);

    /** Execute one measurement attempt and persist success or explicit failure. */
    [[nodiscard]] ReadingRecord RunOnce();

   private:
    StorageRingBuffer& storage_;
    Diagnostics& diagnostics_;
    TimeManager& time_;
    CaptureFn capture_;
    RecognizeFn recognize_;
};

}  // namespace fever
