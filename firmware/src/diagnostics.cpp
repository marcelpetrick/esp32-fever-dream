#include "diagnostics.h"

namespace fever {

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

const DiagnosticsSnapshot& Diagnostics::Snapshot() const { return snapshot_; }

}  // namespace fever
