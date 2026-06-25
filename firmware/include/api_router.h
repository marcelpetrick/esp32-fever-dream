#pragma once

#include <cstdint>
#include <string>

#include "diagnostics.h"
#include "storage_ring_buffer.h"

namespace fever {

/** Minimal HTTP method set understood by the local API router. */
enum class ApiMethod : uint8_t {
    kGet = 0,
    kPost = 1,
};

/** API request shape independent from a concrete ESP-IDF HTTP server. */
struct ApiRequest {
    /** HTTP method. */
    ApiMethod method;
    /** Request path, including optional query string. */
    std::string target;
};

/** API response body and HTTP status code. */
struct ApiResponse {
    /** HTTP status code. */
    int status_code;
    /** JSON response body. */
    std::string body;
};

/** Route API requests over diagnostics and reading storage state. */
class ApiRouter {
   public:
    /** Create a router backed by live storage and diagnostics snapshots. */
    ApiRouter(const StorageRingBuffer& storage, const Diagnostics& diagnostics);

    /** Handle one request and return a JSON response. */
    [[nodiscard]] ApiResponse Handle(const ApiRequest& request) const;

   private:
    [[nodiscard]] ApiResponse HandleReadingsLatest(const std::string& query) const;
    [[nodiscard]] static ApiResponse Json(int status_code, std::string body);

    const StorageRingBuffer& storage_;
    const Diagnostics& diagnostics_;
};

}  // namespace fever
