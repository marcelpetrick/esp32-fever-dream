#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace fever {

/** Camera pixel format after capture. */
enum class CameraPixelFormat : uint8_t {
    kUnknown = 0,
    kJpeg = 1,
    kGrayscale = 2,
};

/** Owned camera frame returned by the camera manager. */
struct CameraFrame {
    /** Encoded or raw frame bytes. */
    std::vector<uint8_t> data;
    /** Frame width in pixels when known. */
    std::size_t width;
    /** Frame height in pixels when known. */
    std::size_t height;
    /** Pixel format of `data`. */
    CameraPixelFormat format;
};

/** Result of a single camera capture attempt. */
struct CameraCaptureResult {
    /** True when `frame` contains a valid capture. */
    bool ok;
    /** Captured frame on success. */
    CameraFrame frame;
    /** Stable diagnostic reason on failure. */
    std::string error;
};

/** Hardware camera facade used by the measurement loop. */
class CameraManager {
   public:
    /** Initialize the configured ESP32-CAM camera hardware. */
    [[nodiscard]] bool Initialize();
    /** Capture one frame from the camera. */
    [[nodiscard]] CameraCaptureResult Capture();
    /** Return the last hardware-facing error. */
    [[nodiscard]] const std::string& LastError() const;

   private:
    std::string last_error_;
    std::atomic_flag capture_in_progress_ = ATOMIC_FLAG_INIT;
};

}  // namespace fever
