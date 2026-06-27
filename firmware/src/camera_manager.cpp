#include "camera_manager.h"

#include <utility>

#ifdef ESP_PLATFORM
#include "app_config.h"
#include "esp_camera_af.h"
#include "esp_camera.h"
#include "esp_log.h"
#endif

namespace fever {
namespace {
#ifdef ESP_PLATFORM
constexpr const char* kTag = "camera_manager";

const char* SensorName(const sensor_t* sensor) {
    if (sensor == nullptr) {
        return "unknown";
    }
    switch (sensor->id.PID) {
        case OV2640_PID:
            return "OV2640";
        case OV3660_PID:
            return "OV3660";
        case OV5640_PID:
            return "OV5640";
        default:
            return "unknown";
    }
}

void InitializeAutofocusIfSupported(sensor_t* sensor) {
    if (sensor == nullptr) {
        ESP_LOGW(kTag, "autofocus: unavailable; no sensor handle");
        return;
    }

    if (!esp_camera_af_is_supported(sensor)) {
        ESP_LOGI(kTag, "autofocus: not supported by %s sensor PID=0x%x", SensorName(sensor),
                 static_cast<unsigned int>(sensor->id.PID));
        return;
    }

    esp_camera_af_config_t autofocus_config = {};
    autofocus_config.mode = ESP_CAMERA_AF_MODE_AUTO;
    autofocus_config.step_size = 10;
    autofocus_config.range_min = 0;
    autofocus_config.range_max = 1023;
    autofocus_config.timeout_ms = 2000;

    const esp_err_t init_result = esp_camera_af_init(sensor, &autofocus_config);
    if (init_result != ESP_OK) {
        ESP_LOGW(kTag, "autofocus: init failed for %s: %s", SensorName(sensor), esp_err_to_name(init_result));
        return;
    }

    esp_camera_af_status_t status = {};
    const esp_err_t status_result = esp_camera_af_get_status(sensor, &status);
    if (status_result == ESP_OK) {
        ESP_LOGI(kTag, "autofocus: enabled for %s raw=0x%02x focused=%s busy=%s", SensorName(sensor), status.raw,
                 status.focused ? "yes" : "no", status.busy ? "yes" : "no");
    } else {
        ESP_LOGI(kTag, "autofocus: enabled for %s", SensorName(sensor));
    }
}
#endif
}  // namespace

bool CameraManager::Initialize() {
#ifdef ESP_PLATFORM
    camera_config_t config = {};
    config.pin_pwdn = config::ai_thinker::kPinPwdn;
    config.pin_reset = config::ai_thinker::kPinReset;
    config.pin_xclk = config::ai_thinker::kPinXclk;
    config.pin_sccb_sda = config::ai_thinker::kPinSiod;
    config.pin_sccb_scl = config::ai_thinker::kPinSioc;
    config.pin_d7 = config::ai_thinker::kPinD7;
    config.pin_d6 = config::ai_thinker::kPinD6;
    config.pin_d5 = config::ai_thinker::kPinD5;
    config.pin_d4 = config::ai_thinker::kPinD4;
    config.pin_d3 = config::ai_thinker::kPinD3;
    config.pin_d2 = config::ai_thinker::kPinD2;
    config.pin_d1 = config::ai_thinker::kPinD1;
    config.pin_d0 = config::ai_thinker::kPinD0;
    config.pin_vsync = config::ai_thinker::kPinVsync;
    config.pin_href = config::ai_thinker::kPinHref;
    config.pin_pclk = config::ai_thinker::kPinPclk;
    config.xclk_freq_hz = 20000000;
    config.ledc_timer = LEDC_TIMER_0;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

    const esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        last_error_ = "esp_camera_init_failed";
        ESP_LOGE(kTag, "camera init failed: 0x%x", static_cast<unsigned int>(err));
        return false;
    }

    sensor_t* sensor = esp_camera_sensor_get();
    if (sensor != nullptr) {
        sensor->set_vflip(sensor, 1);
        sensor->set_hmirror(sensor, 1);
        ESP_LOGI(kTag, "detected sensor: %s PID=0x%x", SensorName(sensor), static_cast<unsigned int>(sensor->id.PID));
        InitializeAutofocusIfSupported(sensor);
    }

    last_error_.clear();
    ESP_LOGI(kTag, "camera initialized");
    return true;
#else
    last_error_ = "camera_unavailable_on_host";
    return false;
#endif
}

CameraCaptureResult CameraManager::Capture() {
    if (capture_in_progress_.test_and_set(std::memory_order_acquire)) {
        return CameraCaptureResult{false, {}, "camera_busy"};
    }
    struct CaptureGuard {
        std::atomic_flag& flag;
        ~CaptureGuard() { flag.clear(std::memory_order_release); }
    } guard{capture_in_progress_};

#ifdef ESP_PLATFORM
    camera_fb_t* frame_buffer = esp_camera_fb_get();
    if (frame_buffer == nullptr) {
        last_error_ = "esp_camera_fb_get_failed";
        return CameraCaptureResult{false, {}, last_error_};
    }

    CameraFrame frame;
    frame.data.assign(frame_buffer->buf, frame_buffer->buf + frame_buffer->len);
    frame.width = frame_buffer->width;
    frame.height = frame_buffer->height;
    frame.format = CameraPixelFormat::kJpeg;
    esp_camera_fb_return(frame_buffer);

    {
        std::lock_guard<std::mutex> lock(latest_frame_mutex_);
        latest_frame_ = frame;
    }
    last_error_.clear();
    return CameraCaptureResult{true, std::move(frame), ""};
#else
    last_error_ = "camera_unavailable_on_host";
    return CameraCaptureResult{false, {}, last_error_};
#endif
}

CameraCaptureResult CameraManager::LatestFrame() const {
    std::lock_guard<std::mutex> lock(latest_frame_mutex_);
    if (latest_frame_.data.empty()) {
        return CameraCaptureResult{false, {}, "capture_not_ready"};
    }
    return CameraCaptureResult{true, latest_frame_, ""};
}

const std::string& CameraManager::LastError() const { return last_error_; }

}  // namespace fever
