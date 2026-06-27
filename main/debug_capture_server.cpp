#include "debug_capture_server.h"

#include <cstddef>
#include <string>

#include "api_router.h"
#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_log.h"

namespace fever {
namespace {

constexpr const char* kTag = "debug_capture";

extern const char kIndexHtmlStart[] asm("_binary_index_html_start");
extern const char kIndexHtmlEnd[] asm("_binary_index_html_end");
extern const char kStylesCssStart[] asm("_binary_styles_css_start");
extern const char kStylesCssEnd[] asm("_binary_styles_css_end");
extern const char kAppJsStart[] asm("_binary_app_js_start");
extern const char kAppJsEnd[] asm("_binary_app_js_end");

CameraManager* g_camera = nullptr;
StorageRingBuffer* g_storage = nullptr;
Diagnostics* g_diagnostics = nullptr;

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

esp_err_t SendJsonString(httpd_req_t* request, int status_code, const std::string& body) {
    SetCorsHeaders(request);
    httpd_resp_set_type(request, "application/json");
    switch (status_code) {
        case 200:
            httpd_resp_set_status(request, "200 OK");
            break;
        case 400:
            httpd_resp_set_status(request, "400 Bad Request");
            break;
        case 404:
            httpd_resp_set_status(request, "404 Not Found");
            break;
        case 405:
            httpd_resp_set_status(request, "405 Method Not Allowed");
            break;
        default:
            httpd_resp_set_status(request, "500 Internal Server Error");
            break;
    }
    return httpd_resp_send(request, body.data(), body.size());
}

esp_err_t OptionsHandler(httpd_req_t* request) {
    SetCorsHeaders(request);
    return httpd_resp_send(request, nullptr, 0);
}

esp_err_t HealthHandler(httpd_req_t* request) { return SendJson(request, 200, "{\"ok\":true}"); }

esp_err_t SendStaticAsset(httpd_req_t* request, const char* content_type, const char* start, const char* end) {
    httpd_resp_set_type(request, content_type);
    httpd_resp_set_hdr(request, "Cache-Control", "no-cache");
    return httpd_resp_send(request, start, static_cast<ssize_t>(end - start));
}

esp_err_t IndexHandler(httpd_req_t* request) {
    return SendStaticAsset(request, "text/html; charset=utf-8", kIndexHtmlStart, kIndexHtmlEnd);
}

esp_err_t StylesHandler(httpd_req_t* request) {
    return SendStaticAsset(request, "text/css; charset=utf-8", kStylesCssStart, kStylesCssEnd);
}

esp_err_t AppScriptHandler(httpd_req_t* request) {
    return SendStaticAsset(request, "application/javascript; charset=utf-8", kAppJsStart, kAppJsEnd);
}

esp_err_t ApiHandler(httpd_req_t* request) {
    if (g_storage == nullptr || g_diagnostics == nullptr) {
        return SendJson(request, 500, "{\"error\":{\"code\":\"api_not_ready\",\"message\":\"API state not registered\"}}");
    }
    ApiRouter router(*g_storage, *g_diagnostics);
    const ApiResponse response = router.Handle(ApiRequest{ApiMethod::kGet, request->uri});
    return SendJsonString(request, response.status_code, response.body);
}

esp_err_t CaptureJpegHandler(httpd_req_t* request) {
    if (g_camera == nullptr) {
        return SendJson(request, 500, "{\"ok\":false,\"error\":\"camera_not_registered\"}");
    }

    const CameraCaptureResult capture = g_camera->LatestFrame();
    if (!capture.ok || capture.frame.format != CameraPixelFormat::kJpeg) {
        ESP_LOGW(kTag, "capture failed: %s", capture.error.c_str());
        if (capture.error == "capture_not_ready") {
            SetCorsHeaders(request);
            httpd_resp_set_type(request, "application/json");
            httpd_resp_set_status(request, "503 Service Unavailable");
            httpd_resp_set_hdr(request, "Retry-After", "1");
            return httpd_resp_sendstr(request, "{\"ok\":false,\"error\":\"capture_not_ready\"}");
        }
        return SendJson(request, 500, "{\"ok\":false,\"error\":\"capture_failed\"}");
    }

    char width[16] = {};
    char height[16] = {};
    snprintf(width, sizeof(width), "%u", static_cast<unsigned int>(capture.frame.width));
    snprintf(height, sizeof(height), "%u", static_cast<unsigned int>(capture.frame.height));

    httpd_resp_set_type(request, "image/jpeg");
    SetCorsHeaders(request);
    httpd_resp_set_hdr(request, "Cache-Control", "no-store");
    httpd_resp_set_hdr(request, "Connection", "close");
    httpd_resp_set_hdr(request, "X-Fever-Frame-Width", width);
    httpd_resp_set_hdr(request, "X-Fever-Frame-Height", height);
    httpd_resp_set_hdr(request, "X-Fever-Capture-Source", "periodic-cache");
    return httpd_resp_send(request, reinterpret_cast<const char*>(capture.frame.data.data()), capture.frame.data.size());
}

}  // namespace

bool StartDebugCaptureServer(CameraManager& camera, StorageRingBuffer& storage, Diagnostics& diagnostics) {
    g_camera = &camera;
    g_storage = &storage;
    g_diagnostics = &diagnostics;

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
    const httpd_uri_t index_uri = {
        .uri = "/",
        .method = HTTP_GET,
        .handler = IndexHandler,
        .user_ctx = nullptr,
    };
    const httpd_uri_t styles_uri = {
        .uri = "/styles.css",
        .method = HTTP_GET,
        .handler = StylesHandler,
        .user_ctx = nullptr,
    };
    const httpd_uri_t app_script_uri = {
        .uri = "/app.js",
        .method = HTTP_GET,
        .handler = AppScriptHandler,
        .user_ctx = nullptr,
    };
    const httpd_uri_t capture_uri = {
        .uri = "/debug/capture.jpg",
        .method = HTTP_GET,
        .handler = CaptureJpegHandler,
        .user_ctx = nullptr,
    };
    const httpd_uri_t api_uri = {
        .uri = "/api/v1/*",
        .method = HTTP_GET,
        .handler = ApiHandler,
        .user_ctx = nullptr,
    };
    const httpd_uri_t options_uri = {
        .uri = "/*",
        .method = HTTP_OPTIONS,
        .handler = OptionsHandler,
        .user_ctx = nullptr,
    };

    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &index_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &styles_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &app_script_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &health_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &capture_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &api_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &options_uri));
    ESP_LOGI(kTag, "debug capture server listening on port 80");
    return true;
}

}  // namespace fever
