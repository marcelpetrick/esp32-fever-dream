#include "api_serializer.h"

#include <cstdio>
#include <sstream>

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
    out << "{\"timestamp\":" << record.timestamp_s << ",\"temperature_c\":";
    if (record.IsSuccess()) {
        char buffer[24];
        std::snprintf(buffer, sizeof(buffer), "%.2f", static_cast<double>(record.temperature_centi_c) / 100.0);
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
        << "\",\"confidence\":" << (static_cast<unsigned int>(record.confidence.value) / 100.0) << "}";
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
                            std::size_t storage_capacity, const ReadingRecord* latest) {
    std::ostringstream out;
    out << "{\"device\":\"esp32-cam-thermometer\",\"firmware_version\":\"" << version::ProjectVersion()
        << "\",\"time_synced\":" << (diagnostics.time_synced ? "true" : "false")
        << ",\"storage_records\":" << storage_count << ",\"storage_capacity_records\":" << storage_capacity
        << ",\"boot_count\":" << diagnostics.boot_count << ",\"capture_failures\":" << diagnostics.capture_failures
        << ",\"recognition_failures\":" << diagnostics.recognition_failures
        << ",\"storage_failures\":" << diagnostics.storage_failures << ",\"wifi_rssi\":" << diagnostics.wifi_rssi
        << ",\"last_reading_status\":\"" << (latest == nullptr ? "none" : ToString(latest->status))
        << "\",\"last_error\":";
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
