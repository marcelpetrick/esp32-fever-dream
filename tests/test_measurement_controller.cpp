#include "measurement_controller.h"
#include "test_support.h"

void TestMeasurementController() {
    fever::StorageRingBuffer storage(4);
    fever::Diagnostics diagnostics;
    fever::TimeManager time;
    time.SetSynchronizedTime(1000U);

    fever::MeasurementController success_controller(
        storage, diagnostics, time,
        []() {
            fever::CameraFrame frame{{1U, 2U, 3U}, 1U, 3U, fever::CameraPixelFormat::kJpeg};
            return fever::CameraCaptureResult{true, frame, ""};
        },
        [](const fever::CameraFrame&) {
            return fever::RecognitionResult{true, {733U, 58U, 160U, 2215, 48U}, fever::ConfidencePercent{93U}, 37U,
                                            fever::ReadingStatus::kOk, ""};
        });

    const fever::ReadingRecord success = success_controller.RunOnce();
    REQUIRE(success.IsSuccess());
    REQUIRE(success.timestamp_s == 1000U);
    REQUIRE(success.co2_ppm == 733U);
    REQUIRE(success.hcho_raw == 58U);
    REQUIRE(success.tvoc_raw == 160U);
    REQUIRE(success.temperature_centi_c == 2215);
    REQUIRE(success.humidity_percent == 48U);
    REQUIRE(success.recognition_duration_ms == 37U);
    REQUIRE(storage.Count() == 1U);
    REQUIRE(diagnostics.PipelineCycle() == 1U);
    REQUIRE(diagnostics.CurrentPipelineStage() == fever::PipelineStage::kWaiting);

    fever::MeasurementController failure_controller(
        storage, diagnostics, time, []() { return fever::CameraCaptureResult{false, {}, "camera_timeout"}; },
        [](const fever::CameraFrame&) {
            return fever::RecognitionResult{true,
                                            {fever::kAqsUnsignedUnavailable, fever::kAqsUnsignedUnavailable,
                                             fever::kAqsUnsignedUnavailable, fever::kTemperatureUnavailable,
                                             fever::kHumidityUnavailable},
                                            fever::ConfidencePercent{0U}, 0U, fever::ReadingStatus::kOk, ""};
        });

    const fever::ReadingRecord failure = failure_controller.RunOnce();
    REQUIRE(!failure.IsSuccess());
    REQUIRE(failure.status == fever::ReadingStatus::kCameraFailed);
    REQUIRE(diagnostics.Snapshot().capture_failures == 1U);
    REQUIRE(storage.Count() == 2U);
    REQUIRE(diagnostics.PipelineCycle() == 2U);
    REQUIRE(diagnostics.CurrentPipelineStage() == fever::PipelineStage::kWaiting);
}
