#include "debug_capture_server.h"

#include <algorithm>
#include <charconv>
#include <cstddef>
#include <string>
#include <string_view>

#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_log.h"

namespace fever {
namespace {

constexpr const char* kTag = "debug_capture";
constexpr std::size_t kQueryBufferSize = 256U;

CameraManager* g_camera = nullptr;

std::string QueryString(httpd_req_t* request) {
    const std::size_t query_length = httpd_req_get_url_query_len(request);
    if (query_length == 0U || query_length >= kQueryBufferSize) {
        return {};
    }

    std::string query(query_length, '\0');
    if (httpd_req_get_url_query_str(request, query.data(), query.size() + 1U) != ESP_OK) {
        return {};
    }
    return query;
}

bool QueryParam(std::string_view query, std::string_view name, std::string* value) {
    std::size_t param_start = 0U;
    while (param_start <= query.size()) {
        const std::size_t param_end = query.find('&', param_start);
        const std::string_view param =
            query.substr(param_start, (param_end == std::string_view::npos ? query.size() : param_end) - param_start);
        const std::size_t equals = param.find('=');
        if (param.substr(0U, equals) == name) {
            *value = equals == std::string_view::npos ? std::string{} : std::string(param.substr(equals + 1U));
            return true;
        }
        if (param_end == std::string_view::npos) {
            break;
        }
        param_start = param_end + 1U;
    }
    return false;
}

bool QueryInt(std::string_view query, std::string_view name, int* value) {
    std::string raw_value;
    if (!QueryParam(query, name, &raw_value)) {
        return false;
    }

    int parsed = 0;
    const auto result = std::from_chars(raw_value.data(), raw_value.data() + raw_value.size(), parsed);
    if (raw_value.empty() || result.ec != std::errc{} || result.ptr != raw_value.data() + raw_value.size()) {
        return false;
    }
    *value = parsed;
    return true;
}

framesize_t ParseFrameSize(const std::string& value) {
    if (value == "qvga") {
        return FRAMESIZE_QVGA;
    }
    if (value == "vga") {
        return FRAMESIZE_VGA;
    }
    if (value == "svga") {
        return FRAMESIZE_SVGA;
    }
    return FRAMESIZE_VGA;
}

void ApplyCameraSettings(std::string_view query) {
    sensor_t* sensor = esp_camera_sensor_get();
    if (sensor == nullptr) {
        return;
    }

    std::string frame_size;
    if (QueryParam(query, "framesize", &frame_size)) {
        sensor->set_framesize(sensor, ParseFrameSize(frame_size));
    }

    int value = 0;
    if (QueryInt(query, "quality", &value)) {
        sensor->set_quality(sensor, std::clamp(value, 4, 63));
    }
    if (QueryInt(query, "brightness", &value)) {
        sensor->set_brightness(sensor, std::clamp(value, -2, 2));
    }
    if (QueryInt(query, "contrast", &value)) {
        sensor->set_contrast(sensor, std::clamp(value, -2, 2));
    }
    if (QueryInt(query, "saturation", &value)) {
        sensor->set_saturation(sensor, std::clamp(value, -2, 2));
    }
    if (QueryInt(query, "aec", &value)) {
        sensor->set_exposure_ctrl(sensor, value != 0 ? 1 : 0);
    }
    if (QueryInt(query, "agc", &value)) {
        sensor->set_gain_ctrl(sensor, value != 0 ? 1 : 0);
    }
    if (QueryInt(query, "awb", &value)) {
        sensor->set_whitebal(sensor, value != 0 ? 1 : 0);
    }
}

void SetCorsHeaders(httpd_req_t* request) {
    httpd_resp_set_hdr(request, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(request, "Access-Control-Allow-Methods", "GET, OPTIONS");
    httpd_resp_set_hdr(request, "Access-Control-Allow-Headers", "Content-Type, Accept");
}

esp_err_t SendJson(httpd_req_t* request, int status_code, const char* body) {
    SetCorsHeaders(request);
    httpd_resp_set_type(request, "application/json");
    httpd_resp_set_status(request, status_code == 200 ? "200 OK" : "500 Internal Server Error");
    return httpd_resp_sendstr(request, body);
}

esp_err_t OptionsHandler(httpd_req_t* request) {
    SetCorsHeaders(request);
    return httpd_resp_send(request, nullptr, 0);
}

esp_err_t HealthHandler(httpd_req_t* request) { return SendJson(request, 200, "{\"ok\":true}"); }

esp_err_t CaptureJpegHandler(httpd_req_t* request) {
    if (g_camera == nullptr) {
        return SendJson(request, 500, "{\"ok\":false,\"error\":\"camera_not_registered\"}");
    }

    const std::string query = QueryString(request);
    ApplyCameraSettings(query);

    camera_fb_t* frame_buffer = esp_camera_fb_get();
    if (frame_buffer == nullptr || frame_buffer->format != PIXFORMAT_JPEG) {
        if (frame_buffer != nullptr) {
            esp_camera_fb_return(frame_buffer);
        }
        ESP_LOGW(kTag, "capture failed");
        return SendJson(request, 500, "{\"ok\":false,\"error\":\"capture_failed\"}");
    }

    char width[16] = {};
    char height[16] = {};
    snprintf(width, sizeof(width), "%u", static_cast<unsigned int>(frame_buffer->width));
    snprintf(height, sizeof(height), "%u", static_cast<unsigned int>(frame_buffer->height));

    httpd_resp_set_type(request, "image/jpeg");
    SetCorsHeaders(request);
    httpd_resp_set_hdr(request, "Cache-Control", "no-store");
    httpd_resp_set_hdr(request, "Connection", "close");
    httpd_resp_set_hdr(request, "X-Fever-Frame-Width", width);
    httpd_resp_set_hdr(request, "X-Fever-Frame-Height", height);
    const esp_err_t send_result =
        httpd_resp_send(request, reinterpret_cast<const char*>(frame_buffer->buf), frame_buffer->len);
    esp_camera_fb_return(frame_buffer);
    return send_result;
}

}  // namespace

bool StartDebugCaptureServer(CameraManager& camera) {
    g_camera = &camera;

    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.uri_match_fn = httpd_uri_match_wildcard;

    httpd_handle_t server = nullptr;
    const esp_err_t start_result = httpd_start(&server, &config);
    if (start_result != ESP_OK) {
        ESP_LOGE(kTag, "http server start failed: 0x%x", static_cast<unsigned int>(start_result));
        return false;
    }

    const httpd_uri_t health_uri = {
        .uri = "/debug/health",
        .method = HTTP_GET,
        .handler = HealthHandler,
        .user_ctx = nullptr,
    };
    const httpd_uri_t capture_uri = {
        .uri = "/debug/capture.jpg",
        .method = HTTP_GET,
        .handler = CaptureJpegHandler,
        .user_ctx = nullptr,
    };
    const httpd_uri_t options_uri = {
        .uri = "/*",
        .method = HTTP_OPTIONS,
        .handler = OptionsHandler,
        .user_ctx = nullptr,
    };

    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &health_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &capture_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &options_uri));
    ESP_LOGI(kTag, "debug capture server listening on port 80");
    return true;
}

}  // namespace fever
