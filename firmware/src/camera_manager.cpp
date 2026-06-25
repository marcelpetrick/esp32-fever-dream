#include "camera_manager.h"

#ifdef ESP_PLATFORM
#include "app_config.h"
#include "esp_camera.h"
#include "esp_log.h"
#endif

namespace fever {
namespace {
#ifdef ESP_PLATFORM
constexpr const char* kTag = "camera_manager";
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
    config.frame_size = FRAMESIZE_SVGA;
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

    last_error_.clear();
    return CameraCaptureResult{true, frame, ""};
#else
    last_error_ = "camera_unavailable_on_host";
    return CameraCaptureResult{false, {}, last_error_};
#endif
}

const std::string& CameraManager::LastError() const { return last_error_; }

}  // namespace fever
