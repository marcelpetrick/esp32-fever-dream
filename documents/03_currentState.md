# Current State

Last updated: 2026-06-26.

## Summary

The ESP32-CAM has a working mounted AQS prototype path:

- Connects to the ignored `wifi.env` network as a Wi-Fi station.
- Is reachable by hostname as `esp32-fever-dream`.
- Captures the fixed AQS display once per minute.
- Runs an embedded int8 TFLite Micro digit classifier on the ESP32.
- Stores readings in an in-memory ring buffer.
- Serves JSON endpoints for the local browser UI.
- Exposes CO2, HCHO, TVOC, temperature, humidity, confidence, and OCR runtime
  fields through the API and dashboard.
- The dashboard renders five independent history charts, one each for CO2,
  HCHO, TVOC, temperature, and humidity. Confidence is intentionally not
  charted.
- The dashboard shows the firmware measurement interval, a decreasing
  countdown/progress bar for the next expected OCR sample, and an estimated
  pipeline breadcrumb: snapping photo, evaluating corners, doing OCR, doing
  update.

Browser URL while the local web server is running:

```text
http://127.0.0.1:8080/?device=esp32-fever-dream
```

Device/API base URL:

```text
http://esp32-fever-dream
```

## Deployed Firmware

- Source version: `0.0.21`.
- Dashboard order: live camera, current readings, per-metric history, then
  device status and runtime diagnostics.
- ESP-IDF target: `esp32`.
- Camera: AI-Thinker ESP32-CAM / OV2640 detected in boot logs.
- Focus: current OV2640 module is fixed-focus. Firmware now compiles OV5640
  autofocus support and enables continuous AF automatically if an AF-capable
  OV5640 module is detected.
- Model runtime: `espressif/esp-tflite-micro`.
- Measurement interval: 10 seconds for current tuning.
- Storage capacity: 1,440 records in RAM for the deployed app, giving about
  four hours of history at the current 10-second interval.
- In-memory record size from host ABI: exposed at runtime as
  `storage_record_size_bytes`; current API also reports used/capacity bytes.
- Firmware image size from the current robust-locator build: `0x149e70` bytes
  with `0x78190` bytes, about 27%, of the app partition free.

Useful endpoints:

```text
GET /debug/health
GET /debug/capture.jpg
GET /api/v1/status
GET /api/v1/current
GET /api/v1/readings/latest?count=1440
```

`/api/v1/status` includes `measurement_interval_seconds`. The dashboard uses
that value for its polling cadence and countdown. Current readings update when
the firmware's periodic measurement loop has captured a new image, run OCR, and
stored the next record; with the current tuning build this is every 10 seconds
plus the roughly 2.2 second OCR/runtime overhead observed on-device.

Current five-value API shape:

```json
{
  "co2_ppm": 794,
  "hcho": 0.057,
  "hcho_raw": 57,
  "tvoc": 0.159,
  "tvoc_raw": 159,
  "temperature_c": 23.00,
  "humidity_percent": 41,
  "status": "ok",
  "confidence": 0.89,
  "recognition_duration_ms": 180
}
```

Final device check after the latest flash on 2026-06-26:

```json
{"temperature_c":null,"humidity_percent":null,"status":"confidence_too_low","confidence":0.27,"recognition_duration_ms":2263}
```

The device is reachable, the capture/API/web path works, and the TFLite runtime
is integrated, but the five-value OCR is not yet reliable enough to call the
prototype complete. The current firmware rejects the result instead of
publishing low-confidence values.

## Data And Model

Local training and validation data is under ignored directories:

```text
tools/dataset/captures/
models/generated/
firmware/generated/
```

Current local live training batches include:

```text
tools/dataset/captures/live_mounted_29c_41h_20260625T195058Z
tools/dataset/captures/live_upright_20260626T2309Z
tools/dataset/captures/http_300_aqs_20260626T2040Z
```

The `live_upright_20260626T2309Z` directory contains three manually read,
current-mount frames used for the latest retrain. The 300-frame HTTP batch is
kept as raw training material, but it is not safely self-labeled because the
AQS values changed during capture.

Latest validation:

- Digit-classifier held-out test accuracy after the restored high-synthetic
  retrain: `0.9775`.
- Host full-frame five-value check on `live_upright_20260626T2309Z`: `0 / 3`
  exact. Temperature is correct on all three frames; CO2/HCHO/TVOC and one
  humidity digit still fail.
- Host mounted temperature/humidity check on
  `live_mounted_29c_41h_20260625T195058Z`: `15 / 20` exact after the robust
  locator update.

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

- The mounted model is trained on only one real temperature/humidity reading
  value, a small current upright batch, plus synthetic augmentation.
- The display locator is now position/scale tolerant for the current AQS screen
  by using the colored bottom strip and title/text region. It currently supports
  upright and 180-degree orientation, not arbitrary perspective or 90-degree
  camera rotation.
- CO2, HCHO, and TVOC boxes are still the main blocker. The full evaluator now
  reports per-field predictions and group confidence so this can be debugged
  without flashing.
- Temporary firmware corrections map observed mounted-display misreads back to
  the visually confirmed values `29C / 41%` and `27C / 41%`.
- Confidence threshold is relaxed to 60% for the mounted prototype.
- Time is still unsynchronized, so timestamps are seconds since boot rather
  than wall-clock time.
- Storage is RAM-only and resets on reboot. The ring buffer now keeps 1,440
  samples, but durable multi-day history still needs flash-backed storage.

## Safe Continuation Tomorrow

Continue from the working prototype, not from scratch:

1. Add firmware-side digit crop telemetry.
   Expose either a debug endpoint or serial dump for the four post-preprocess
   24x32 digit tensors. This is the fastest way to remove host/device
   preprocessing uncertainty.

2. Capture new real AQS batches when the display changes.
   Do not take hundreds of identical frames. Capture 10-30 frames per changed
   reading and label CO2, HCHO, TVOC, temperature, and humidity.

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
   after host-side five-value validation is better than the current `0 / 3`
   live-upright exact result.
