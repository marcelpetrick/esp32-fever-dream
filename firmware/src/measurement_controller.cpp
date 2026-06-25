#include "measurement_controller.h"

#include <algorithm>
#include <cstdint>

namespace fever {

MeasurementController::MeasurementController(StorageRingBuffer& storage, Diagnostics& diagnostics, TimeManager& time,
                                             CaptureFn capture, RecognizeFn recognize)
    : storage_(storage),
      diagnostics_(diagnostics),
      time_(time),
      capture_(std::move(capture)),
      recognize_(std::move(recognize)) {}

ReadingRecord MeasurementController::RunOnce() {
    const TimestampState timestamp = time_.Now();
    const CameraCaptureResult capture = capture_();
    if (!capture.ok) {
        diagnostics_.RecordCaptureFailure(capture.error);
        ReadingFlags flags = timestamp.synced ? ReadingFlags::kNone : ReadingFlags::kTimeEstimated;
        ReadingRecord record =
            ReadingRecord::Failure(timestamp.timestamp_s, ReadingStatus::kCameraFailed, ConfidencePercent{0U}, flags);
        if (!storage_.Append(record)) {
            diagnostics_.RecordStorageFailure("append_failed");
        }
        return record;
    }

    const RecognitionResult recognition = recognize_(capture.frame);
    ReadingFlags flags = timestamp.synced ? ReadingFlags::kRecognitionHybrid
                                          : (ReadingFlags::kRecognitionHybrid | ReadingFlags::kTimeEstimated);
    ReadingRecord record =
        recognition.ok
            ? ReadingRecord::Success(timestamp.timestamp_s, recognition.temperature_centi_c, recognition.confidence,
                                     flags, recognition.humidity_percent,
                                     static_cast<uint16_t>(std::min<uint32_t>(recognition.recognition_duration_ms,
                                                                              UINT16_MAX)))
            : ReadingRecord::Failure(timestamp.timestamp_s, recognition.status, recognition.confidence, flags,
                                     static_cast<uint16_t>(std::min<uint32_t>(recognition.recognition_duration_ms,
                                                                              UINT16_MAX)));

    if (!recognition.ok) {
        diagnostics_.RecordRecognitionFailure(recognition.error);
    }
    if (!storage_.Append(record)) {
        diagnostics_.RecordStorageFailure("append_failed");
    }
    return record;
}

}  // namespace fever
