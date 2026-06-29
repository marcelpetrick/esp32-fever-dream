#include "api_serializer.h"

#include <cstdio>
#include <sstream>

#include "app_config.h"
#include "version.h"

namespace fever {
namespace {

void AppendJsonString(std::ostringstream& out, const std::string& value) {
    out << '"';
    for (const char ch : value) {
        switch (ch) {
            case '"':
                out << "\\\"";
                break;
            case '\\':
                out << "\\\\";
                break;
            case '\n':
                out << "\\n";
                break;
            case '\r':
                out << "\\r";
                break;
            case '\t':
                out << "\\t";
                break;
            default:
                out << ch;
                break;
        }
    }
    out << '"';
}

void AppendRecord(std::ostringstream& out, const ReadingRecord& record) {
    out << "{\"timestamp\":" << record.timestamp_s << ",\"co2_ppm\":";
    if (const auto co2 = record.Co2Ppm(); co2.has_value()) {
        out << static_cast<unsigned int>(*co2);
    } else {
        out << "null";
    }
    out << ",\"hcho\":";
    if (const auto hcho = record.HchoRaw(); hcho.has_value()) {
        char buffer[24];
        std::snprintf(buffer, sizeof(buffer), "%.3f", static_cast<double>(*hcho) / 1000.0);
        out << buffer;
    } else {
        out << "null";
    }
    out << ",\"hcho_raw\":";
    if (const auto hcho = record.HchoRaw(); hcho.has_value()) {
        out << static_cast<unsigned int>(*hcho);
    } else {
        out << "null";
    }
    out << ",\"tvoc\":";
    if (const auto tvoc = record.TvocRaw(); tvoc.has_value()) {
        char buffer[24];
        std::snprintf(buffer, sizeof(buffer), "%.3f", static_cast<double>(*tvoc) / 1000.0);
        out << buffer;
    } else {
        out << "null";
    }
    out << ",\"tvoc_raw\":";
    if (const auto tvoc = record.TvocRaw(); tvoc.has_value()) {
        out << static_cast<unsigned int>(*tvoc);
    } else {
        out << "null";
    }
    out << ",\"temperature_c\":";
    if (const auto temperature = record.TemperatureCelsius(); temperature.has_value()) {
        char buffer[24];
        std::snprintf(buffer, sizeof(buffer), "%.2f", static_cast<double>(*temperature));
        out << buffer;
    } else {
        out << "null";
    }
    out << ",\"humidity_percent\":";
    if (const auto humidity = record.HumidityPercent(); humidity.has_value()) {
        out << static_cast<unsigned int>(*humidity);
    } else {
        out << "null";
    }
    out << ",\"status\":\"" << ToString(record.status)
        << "\",\"confidence\":" << (static_cast<unsigned int>(record.confidence.value) / 100.0)
        << ",\"recognition_duration_ms\":" << record.recognition_duration_ms << "}";
}

}  // namespace

std::string SerializeCurrent(const ReadingRecord& record) {
    std::ostringstream out;
    AppendRecord(out, record);
    return out.str();
}

std::string SerializeReadings(const std::vector<ReadingRecord>& records) {
    std::ostringstream out;
    out << "{\"readings\":[";
    for (std::size_t i = 0; i < records.size(); ++i) {
        if (i != 0U) {
            out << ',';
        }
        AppendRecord(out, records[i]);
    }
    out << "]}";
    return out.str();
}

std::string SerializeStatus(const DiagnosticsSnapshot& diagnostics, std::size_t storage_count,
                            std::size_t storage_capacity, std::size_t storage_used_bytes,
                            std::size_t storage_capacity_bytes, std::size_t storage_record_size_bytes,
                            const ReadingRecord* latest, PipelineStage pipeline_stage, uint32_t pipeline_cycle) {
    std::ostringstream out;
    out << "{\"device\":\"esp32-cam-aqs\",\"display\":\"AQS\",\"firmware_version\":\"" << version::ProjectVersion()
        << "\",\"time_synced\":" << (diagnostics.time_synced ? "true" : "false")
        << ",\"storage_records\":" << storage_count << ",\"storage_capacity_records\":" << storage_capacity
        << ",\"storage_backend\":\"psram_ring_buffer\""
        << ",\"storage_record_size_bytes\":" << storage_record_size_bytes
        << ",\"storage_used_bytes\":" << storage_used_bytes << ",\"storage_capacity_bytes\":" << storage_capacity_bytes
        << ",\"measurement_interval_seconds\":" << config::kMeasurementIntervalSeconds
        << ",\"storage_retention_minutes\":" << (storage_capacity * config::kMeasurementIntervalSeconds / 60U)
        << ",\"storage_retention_hours\":"
        << (static_cast<double>(storage_capacity * config::kMeasurementIntervalSeconds) / 3600.0)
        << ",\"boot_count\":" << diagnostics.boot_count << ",\"capture_failures\":" << diagnostics.capture_failures
        << ",\"recognition_failures\":" << diagnostics.recognition_failures
        << ",\"storage_failures\":" << diagnostics.storage_failures << ",\"wifi_rssi\":" << diagnostics.wifi_rssi
        << ",\"recognition_min_confidence\":"
        << (static_cast<unsigned int>(config::kRecognitionMinConfidencePercent) / 100.0)
        << ",\"recognition_min_confidence_percent\":"
        << static_cast<unsigned int>(config::kRecognitionMinConfidencePercent) << ",\"pipeline_stage\":\""
        << ToString(pipeline_stage) << "\""
        << ",\"pipeline_stage_index\":" << static_cast<unsigned int>(pipeline_stage)
        << ",\"pipeline_cycle\":" << pipeline_cycle << ",\"last_reading_status\":\""
        << (latest == nullptr ? "none" : ToString(latest->status)) << "\",\"last_error\":";
    AppendJsonString(out, diagnostics.last_error);
    out << "}";
    return out.str();
}

std::string SerializeError(ApiError error) {
    std::ostringstream out;
    out << "{\"error\":{\"code\":";
    AppendJsonString(out, error.code == nullptr ? "unknown" : error.code);
    out << ",\"message\":";
    AppendJsonString(out, error.message == nullptr ? "" : error.message);
    out << "}}";
    return out.str();
}

}  // namespace fever
