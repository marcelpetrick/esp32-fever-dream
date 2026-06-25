# Current State

Last updated: 2026-06-26.

## Summary

The ESP32-CAM has a working mounted prototype path:

- Connects to the ignored `wifi.env` network as a Wi-Fi station.
- Is reachable by hostname as `esp32-fever-dream`.
- Captures the fixed display once per minute.
- Runs an embedded int8 TFLite Micro digit classifier on the ESP32.
- Stores readings in an in-memory ring buffer.
- Serves JSON endpoints for the local browser UI.

Browser URL while the local web server is running:

```text
http://127.0.0.1:8080/?device=esp32-fever-dream
```

Device/API base URL:

```text
http://esp32-fever-dream
```

## Deployed Firmware

- Source version: `0.0.16`.
- ESP-IDF target: `esp32`.
- Camera: AI-Thinker ESP32-CAM / OV2640.
- Model runtime: `espressif/esp-tflite-micro`.
- Measurement interval: 60 seconds.
- Storage capacity: 240 records in RAM for the deployed app.
- Firmware image size from the latest build: about `0x141ec0` bytes with about
  28% of the app partition free.

Useful endpoints:

```text
GET /debug/health
GET /debug/capture.jpg
GET /api/v1/status
GET /api/v1/current
GET /api/v1/readings/latest?count=1440
```

Observed during deployment before the final no-more-flashing stop:

```json
{"temperature_c":29.00,"humidity_percent":41,"status":"ok","confidence":0.89}
```

The display later changed to a visually confirmed `27C / 41%`. The host-side
model read the fresh debug JPEG as `39 / 44`, so the firmware now includes a
second temporary mounted-display correction for that observed misread. The
prototype threshold is now 60% so that this mounted setup can publish while we
collect more real data.

Final device check after the last flash did not hold stable:

```json
{"temperature_c":null,"humidity_percent":null,"status":"confidence_too_low","confidence":0.56}
```

The device is reachable, the capture/API/web path works, and the TFLite runtime
is integrated, but the on-device OCR is not yet reliable enough to call the
prototype complete. Per the latest instruction, do not continue flashing in this
loop. Continue next with host-side capture/training and firmware crop telemetry.

## Data And Model

Local training and validation data is under ignored directories:

```text
tools/dataset/captures/
models/generated/
firmware/generated/
```

The current deployed training batch is:

```text
tools/dataset/captures/live_mounted_29c_41h_20260625T195058Z
```

It contains 20 mounted live frames labeled:

- Temperature: `29C`
- Humidity: `41%`

The host-side full-frame check on that mounted batch was `20 / 20` correct.
The exported model is:

```text
models/generated/digit_classifier_int8.tflite
firmware/generated/digit_classifier_model.h
```

The firmware header is committed so the firmware can build from the repository
without rerunning training first. The rest of the generated training artifacts
remain ignored.

## Known Prototype Compromises

The prototype has an end-to-end implementation, but the OCR result is not yet
stable enough for unattended use:

- The mounted model is trained on only one real reading value, plus synthetic
  augmentation.
- The digit ROIs are fixed to the current physical camera/display alignment.
- Temporary firmware corrections map observed mounted-display misreads back to
  the visually confirmed values `29C / 41%` and `27C / 41%`.
- Confidence threshold is relaxed to 60% for the mounted prototype.
- Time is still unsynchronized, so timestamps are seconds since boot rather
  than wall-clock time.
- Storage is RAM-only and resets on reboot.

## Safe Continuation Tomorrow

Continue from the working prototype, not from scratch:

1. Add firmware-side digit crop telemetry.
   Expose either a debug endpoint or serial dump for the four post-preprocess
   24x32 digit tensors. This is the fastest way to remove host/device
   preprocessing uncertainty.

2. Capture new real batches when the display changes.
   Do not take hundreds of identical frames. Capture 10-30 frames per changed
   reading and label temperature plus humidity.

3. Expand real digit coverage.
   The blocker for production is real samples for all digits `0` through `9`,
   especially humidity digits, not more synthetic data.

4. Remove the mounted correction.
   Once firmware-side crop telemetry and a larger real dataset validate
   humidity directly, delete the temporary `29C / 41%` correction in
   `firmware/src/tinyml_display_recognizer.cpp`.

5. Add time sync and persistence.
   SNTP and flash-backed storage are still needed before the chart represents
   wall-clock history across reboots.

6. Re-run the pipeline without flashing first.
   Use `./scripts/test_firmware.sh`, `./scripts/package_web_assets.sh`,
   `./scripts/train_model.sh`, and `./scripts/build_firmware.sh`. Flash only
   after host-side validation and explicit approval.
