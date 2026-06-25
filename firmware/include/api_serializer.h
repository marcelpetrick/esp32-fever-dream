#pragma once

#include <cstddef>
#include <string>
#include <vector>

#include "diagnostics.h"
#include "reading_record.h"

namespace fever {

/** Structured API error payload used to avoid swapped string parameters. */
struct ApiError {
    /** Stable machine-readable error code. */
    const char* code;
    /** Human-readable diagnostic message. */
    const char* message;
};

/** Serialize the latest reading as the `/api/v1/current` response body. */
[[nodiscard]] std::string SerializeCurrent(const ReadingRecord& record);
/** Serialize a chronological reading list as the `/api/v1/readings` response body. */
[[nodiscard]] std::string SerializeReadings(const std::vector<ReadingRecord>& records);
/** Serialize device health and storage state as the `/api/v1/status` response body. */
[[nodiscard]] std::string SerializeStatus(const DiagnosticsSnapshot& diagnostics, std::size_t storage_count,
                                          std::size_t storage_capacity, const ReadingRecord* latest);
/** Serialize a structured API error response. */
[[nodiscard]] std::string SerializeError(ApiError error);

}  // namespace fever
