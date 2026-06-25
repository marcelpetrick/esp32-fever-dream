#pragma once

#include <cstdint>
#include <string>

namespace fever {

/** Snapshot of device health counters and last-known runtime state. */
struct DiagnosticsSnapshot {
    /** Number of boots observed by this diagnostics instance. */
    uint32_t boot_count;
    /** Number of camera capture failures. */
    uint32_t capture_failures;
    /** Number of recognition failures. */
    uint32_t recognition_failures;
    /** Number of storage write/read failures. */
    uint32_t storage_failures;
    /** Last known Wi-Fi RSSI in dBm, or zero if unknown. */
    int32_t wifi_rssi;
    /** True when the current timestamp source is synchronized. */
    bool time_synced;
    /** Most recent diagnostic error string. */
    std::string last_error;
};

/** Mutable diagnostics accumulator for firmware runtime health. */
class Diagnostics {
   public:
    /** Record a boot event. */
    void RecordBoot();
    /** Record a camera capture failure and store the reason. */
    void RecordCaptureFailure(const std::string& error);
    /** Record a recognition failure and store the reason. */
    void RecordRecognitionFailure(const std::string& error);
    /** Record a storage failure and store the reason. */
    void RecordStorageFailure(const std::string& error);
    /** Set the last known Wi-Fi RSSI in dBm. */
    void SetWifiRssi(int32_t rssi);
    /** Set whether device time is synchronized. */
    void SetTimeSynced(bool synced);

    /** Return the current diagnostics snapshot. */
    [[nodiscard]] const DiagnosticsSnapshot& Snapshot() const;

   private:
    DiagnosticsSnapshot snapshot_{};
};

}  // namespace fever
