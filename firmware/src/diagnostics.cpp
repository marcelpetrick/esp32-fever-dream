#include "diagnostics.h"

namespace fever {

const char* ToString(PipelineStage stage) {
    switch (stage) {
        case PipelineStage::kWaiting:
            return "waiting";
        case PipelineStage::kCaptureImage:
            return "capture_image";
        case PipelineStage::kDecodeImage:
            return "decode_image";
        case PipelineStage::kLocateDisplay:
            return "locate_display";
        case PipelineStage::kRunOcr:
            return "run_ocr";
        case PipelineStage::kValidateAndSave:
            return "validate_and_save";
    }
    return "waiting";
}

void Diagnostics::RecordBoot() { ++snapshot_.boot_count; }

void Diagnostics::RecordCaptureFailure(const std::string& error) {
    ++snapshot_.capture_failures;
    snapshot_.last_error = error;
}

void Diagnostics::RecordRecognitionFailure(const std::string& error) {
    ++snapshot_.recognition_failures;
    snapshot_.last_error = error;
}

void Diagnostics::RecordStorageFailure(const std::string& error) {
    ++snapshot_.storage_failures;
    snapshot_.last_error = error;
}

void Diagnostics::SetWifiRssi(int32_t rssi) { snapshot_.wifi_rssi = rssi; }

void Diagnostics::SetTimeSynced(bool synced) { snapshot_.time_synced = synced; }

void Diagnostics::BeginPipelineCycle() {
    pipeline_cycle_.fetch_add(1U, std::memory_order_relaxed);
    pipeline_stage_.store(PipelineStage::kCaptureImage, std::memory_order_release);
}

void Diagnostics::SetPipelineStage(PipelineStage stage) { pipeline_stage_.store(stage, std::memory_order_release); }

PipelineStage Diagnostics::CurrentPipelineStage() const { return pipeline_stage_.load(std::memory_order_acquire); }

uint32_t Diagnostics::PipelineCycle() const { return pipeline_cycle_.load(std::memory_order_relaxed); }

const DiagnosticsSnapshot& Diagnostics::Snapshot() const { return snapshot_; }

}  // namespace fever
