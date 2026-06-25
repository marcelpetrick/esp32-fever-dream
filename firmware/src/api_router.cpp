#include "api_router.h"

#include <algorithm>
#include <charconv>
#include <string_view>

#include "api_serializer.h"

namespace fever {
namespace {

constexpr std::size_t kDefaultLatestCount = 60U;
constexpr std::size_t kMaxReadingsLimit = 10000U;

std::string_view PathOnly(std::string_view target) {
    const std::size_t query_start = target.find('?');
    return target.substr(0U, query_start);
}

std::string QueryOnly(std::string_view target) {
    const std::size_t query_start = target.find('?');
    if (query_start == std::string_view::npos) {
        return {};
    }
    return std::string(target.substr(query_start + 1U));
}

bool ParseCount(const std::string& query, std::size_t* count) {
    if (query.empty()) {
        *count = kDefaultLatestCount;
        return true;
    }

    const std::string_view query_view(query);
    std::size_t param_start = 0U;
    while (param_start <= query_view.size()) {
        const std::size_t param_end = query_view.find('&', param_start);
        const std::string_view param = query_view.substr(
            param_start, (param_end == std::string_view::npos ? query_view.size() : param_end) - param_start);
        const std::size_t equals = param.find('=');
        const std::string_view name = param.substr(0U, equals);
        if (name == "count") {
            const std::string_view raw_value =
                equals == std::string_view::npos ? std::string_view{} : param.substr(equals + 1U);
            std::size_t parsed = 0U;
            const auto result = std::from_chars(raw_value.data(), raw_value.data() + raw_value.size(), parsed);
            if (raw_value.empty() || result.ec != std::errc{} || result.ptr != raw_value.data() + raw_value.size()) {
                return false;
            }
            if (parsed == 0U || parsed > kMaxReadingsLimit) {
                return false;
            }
            *count = parsed;
            return true;
        }
        if (param_end == std::string_view::npos) {
            break;
        }
        param_start = param_end + 1U;
    }

    *count = kDefaultLatestCount;
    return true;
}

}  // namespace

ApiRouter::ApiRouter(const StorageRingBuffer& storage, const Diagnostics& diagnostics)
    : storage_(storage), diagnostics_(diagnostics) {}

ApiResponse ApiRouter::Handle(const ApiRequest& request) const {
    if (request.method != ApiMethod::kGet) {
        return Json(405, SerializeError(ApiError{"method_not_allowed", "Only GET is supported for this endpoint."}));
    }

    const std::string_view path = PathOnly(request.target);
    if (path == "/api/v1/status") {
        const auto latest = storage_.Latest();
        return Json(200, SerializeStatus(diagnostics_.Snapshot(), storage_.Count(), storage_.Capacity(),
                                         latest.has_value() ? &(*latest) : nullptr));
    }
    if (path == "/api/v1/current") {
        const auto latest = storage_.Latest();
        if (!latest.has_value()) {
            return Json(404, SerializeError(ApiError{"not_found", "No readings are stored yet."}));
        }
        return Json(200, SerializeCurrent(*latest));
    }
    if (path == "/api/v1/readings" || path == "/api/v1/readings/latest") {
        return HandleReadingsLatest(QueryOnly(request.target));
    }
    if (path == "/api/v1/diagnostics") {
        const auto latest = storage_.Latest();
        return Json(200, SerializeStatus(diagnostics_.Snapshot(), storage_.Count(), storage_.Capacity(),
                                         latest.has_value() ? &(*latest) : nullptr));
    }

    return Json(404, SerializeError(ApiError{"not_found", "Endpoint not found."}));
}

ApiResponse ApiRouter::HandleReadingsLatest(const std::string& query) const {
    std::size_t count = kDefaultLatestCount;
    if (!ParseCount(query, &count)) {
        return Json(400,
                    SerializeError(ApiError{"invalid_parameter", "Parameter 'count' must be between 1 and 10000."}));
    }
    return Json(200, SerializeReadings(storage_.ReadChronological(count)));
}

ApiResponse ApiRouter::Json(int status_code, std::string body) { return ApiResponse{status_code, std::move(body)}; }

}  // namespace fever
