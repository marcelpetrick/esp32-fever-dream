# ESP32 Fever Dream Software Development Plan

## 1. Direction

Build a fully local ESP32-CAM temperature readout device that captures a fixed digital thermometer once per minute, recognizes the displayed value, stores readings in bounded local storage, and serves both a local dashboard and REST-like API directly from the device.

The project should stay inspectable and reproducible: GPLv3 licensing, pinned stable dependencies, signed conventional commits, single-source versioning, documented interfaces, a local quality pipeline, and review cycles with tracked findings.

## 2. Product Target

The first complete system should provide:

- One measurement attempt every 60 seconds.
- Explicit records for successful and failed readings.
- On-device image preprocessing and recognition.
- Local bounded ring-buffer storage.
- Local web dashboard with current value, history chart, status, diagnostics, light/dark mode, and theme selection.
- Versioned API under `/api/v1/`.
- No cloud dependency during normal operation.
- Stable 24-hour unattended operation.

Initial non-goals:

- General OCR.
- Arbitrary thermometer layouts.
- Cloud sync.
- Mobile apps.
- Heavy frontend frameworks.
- Large neural models.
- Multi-camera support.

## 3. Baseline Technical Choices

These are the default choices until evidence shows they should change:

- Firmware platform: ESP-IDF, latest stable release, with dependencies pinned.
- Language: C/C++ for firmware, Python for local tooling, shell for pipeline scripts.
- Camera target: ESP32-CAM class board matching the hardware notes from `/home/mpetrick/repos/esp32Collection/esp32cam/`.
- Recognition strategy: hybrid pipeline, starting with classical seven-segment recognition and adding TinyML only if measured accuracy requires it.
- Storage: fixed-size binary records in a bounded ring buffer, backed by LittleFS or a raw partition after prototype comparison.
- Time: UTC internally, browser-local rendering in the dashboard.
- Frontend: static HTML/CSS/vanilla JavaScript, local assets only, canvas/SVG charting.
- API format: JSON for public endpoints, compact binary only internally unless later needed.

## 4. Repository Bootstrap

Create the implementation repository around the existing documents.

Required files:

```text
README.md
LICENSE
.gitignore
VERSION
platformio.ini or ESP-IDF project files
documents/
firmware/
web/
tools/
scripts/
reports/
```

Required policy:

- License: GPLv3.
- Commit style: conventional commits with meaningful details.
- Commit signature: all commits signed off with `Signed-off-by`.
- Versioning: SemVer, single source of truth in `VERSION`.
- Initial version: `0.0.0`.
- Version increment rule: increase the patch version by one for each commit unless explicitly directed otherwise.
- Secrets: never commit Wi-Fi credentials or local hardware credentials.

`.gitignore` must cover at least:

- Build outputs.
- ESP-IDF and PlatformIO generated folders.
- Python virtual environments and caches.
- Local configuration files.
- Captured datasets that are too large or private, unless intentionally tracked.
- Model training artifacts that are generated from tracked source inputs.

## 5. Target Structure

```text
firmware/
  include/
    app_config.h
    version.h
    camera_manager.h
    image_preprocessor.h
    recognition.h
    storage_ring_buffer.h
    time_manager.h
    api_server.h
    web_server.h
    diagnostics.h
  src/
    main.cpp
    camera_manager.cpp
    image_preprocessor.cpp
    recognition.cpp
    storage_ring_buffer.cpp
    time_manager.cpp
    api_server.cpp
    web_server.cpp
    diagnostics.cpp
  test/
    test_ring_buffer.cpp
    test_record_encoding.cpp
    test_value_validation.cpp
    test_api_parameters.cpp
  partitions.csv

web/
  index.html
  styles.css
  app.js
  assets/

tools/
  dataset/
  recognition_eval/
  model_training/
  model_export/

scripts/
  check_all.sh
  format_cpp.sh
  lint_cpp.sh
  static_analysis.sh
  build_firmware.sh
  test_firmware.sh
  package_web_assets.sh
  collect_dataset.sh
  train_model.sh
  convert_model.sh
  flash_device.sh
  monitor_serial.sh

reports/
  review_log.md
  model_eval.md
  static_analysis.md
```

## 6. Phase 0: Foundation

Goal: make the repository buildable, licensed, versioned, and maintainable before product code grows.

Tasks:

- Add GPLv3 license.
- Add `.gitignore`.
- Add `VERSION` as the single source of truth.
- Choose ESP-IDF project layout and pin the SDK version.
- Add initial firmware skeleton with `app_main`, version reporting, and serial logging.
- Add formatting configuration using Google-style C++ with 4-space indentation and 120-character line limit.
- Add Doxygen configuration and document public interfaces from the first module onward.
- Add `scripts/check_all.sh` as the single local pipeline entrypoint.
- Add minimal unit test wiring.

Acceptance:

- A clean checkout can run the local pipeline.
- Firmware skeleton builds without warnings.
- The version is available to firmware and documentation tooling from one source.
- No local secrets are tracked.

## 7. Phase 1: Camera Feasibility

Goal: prove the target ESP32-CAM can capture readable thermometer images in the intended physical setup.

Tasks:

- Read hardware details from `/home/mpetrick/repos/esp32Collection/esp32cam/`.
- Configure camera pins, frame size, pixel format, exposure, gain, and white balance.
- Capture still images from the real mounting position.
- Add a debug endpoint or serial/Wi-Fi download path for latest capture.
- Document camera settings and region of interest.
- Store representative sample images locally for development.

Acceptance:

- Captures consistently show the thermometer display.
- Region of interest is documented.
- Capture failures produce explicit diagnostics.
- Build remains warning-free.

## 8. Phase 2: Recognition Prototype

Goal: determine whether deterministic seven-segment recognition is sufficient.

Tasks:

- Implement desktop tooling to crop the region of interest.
- Convert to grayscale, normalize, threshold, and segment digits.
- Detect decimal point and optional sign.
- Implement rule-based seven-segment decoding.
- Compare decoded values against labels.
- Produce `reports/model_eval.md` even if no ML model is used.

Acceptance:

- Full-reading accuracy is measured on real captures.
- Failure cases are classified instead of silently ignored.
- A decision is recorded: classical-only, TinyML, or hybrid.

Default threshold:

- Per-digit accuracy: at least 99% on controlled validation images.
- Full-reading accuracy: at least 98%.
- Invalid or ambiguous images must be rejected explicitly.

## 9. Phase 3: TinyML Fallback

Goal: add a compact classifier only if classical recognition is not reliable enough.

Tasks:

- Create labeled digit crops from real captures.
- Train a small per-digit classifier.
- Quantize to int8.
- Export a firmware-compatible model artifact.
- Integrate inference behind the recognition interface.
- Measure flash, RAM, latency, and accuracy.

Acceptance:

- Model artifact and evaluation report are reproducible from scripts.
- Inference fits ESP32 memory constraints.
- Recognition still returns explicit status, confidence, and error metadata.
- No generic OCR or large model dependency is introduced.

## 10. Phase 4: Persistent Storage

Goal: persist readings locally with bounded storage and power-loss-aware behavior.

Record fields:

- Timestamp.
- Temperature in centi-degrees Celsius.
- Status code.
- Confidence percentage.
- Flags for time validity, recognition source, and diagnostics.

Tasks:

- Define fixed-size binary record format.
- Implement append, chronological reads, latest read, and wraparound.
- Store metadata: write index, count, capacity, schema version, checksum.
- Recover metadata by scanning records when metadata is corrupt.
- Add unit tests for wraparound, encoding, decoding, corruption, and boundary conditions.

Acceptance:

- Appending is O(1).
- Oldest records are overwritten when capacity is reached.
- Corrupt metadata does not destroy valid readings.
- Unit tests cover storage behavior.

## 11. Phase 5: API

Goal: expose stable local data access under `/api/v1/`.

Endpoints:

```text
GET  /api/v1/status
GET  /api/v1/current
GET  /api/v1/readings
GET  /api/v1/readings/latest?count=60
GET  /api/v1/config
POST /api/v1/config
GET  /api/v1/diagnostics
POST /api/v1/capture
```

Tasks:

- Implement JSON serialization with bounded response sizes.
- Validate all query parameters.
- Return clear error payloads for invalid requests.
- Protect configuration writes before use on untrusted networks.
- Ensure API requests cannot block the measurement loop for too long.

Acceptance:

- Current and historical readings are available.
- Failed readings are represented explicitly.
- Invalid parameters return structured errors.
- Large historical responses require limits.

## 12. Phase 6: Local Dashboard

Goal: ship a lightweight web interface served by the ESP32.

Tasks:

- Build static dashboard assets without external CDN dependencies.
- Show current temperature, timestamp, confidence, status, and device health.
- Render historical chart client-side.
- Add time range controls for last hour, 6 hours, 24 hours, and 7 days.
- Add light/dark mode and at least one additional color theme.
- Add diagnostics view for failures, storage, Wi-Fi, timing, and firmware version.
- Package assets for flash, using gzip compression if useful.

Acceptance:

- Dashboard works on desktop and mobile browsers.
- The UI remains usable without internet access.
- Asset size fits the flash partition budget.
- The chart handles failed readings clearly.

## 13. Phase 7: Periodic Operation

Goal: integrate capture, recognition, storage, API, and dashboard into one-minute measurement cycles.

Tasks:

- Implement scheduler with drift correction for always-on prototype.
- Add deep sleep after the core loop is stable, if the power target requires it.
- Add time synchronization through NTP when Wi-Fi is available.
- Fall back to estimated time progression when time is not synchronized.
- Record failures for camera, preprocessing, recognition, storage, Wi-Fi, and time issues.
- Add watchdog-friendly timeouts.

Acceptance:

- One measurement is attempted every 60 seconds.
- Missed or failed measurements are stored as failure records.
- System recovers from Wi-Fi loss.
- System survives reboot without losing valid historical data.

## 14. Phase 8: Hardening

Goal: turn the prototype into a reliable device.

Tasks:

- Fix all build warnings.
- Run static analysis and address high-severity findings immediately.
- Add code coverage measurement where practical, with 90% as the target.
- Add Doxygen coverage checks for public interfaces.
- Add long-run tests: 24-hour run, storage wraparound, power loss, Wi-Fi outage, lighting variation.
- Add memory and flash budget reporting.
- Review all API input handling and buffer boundaries.

Acceptance:

- `scripts/check_all.sh` passes.
- 24-hour unattended test passes.
- High-severity review findings are fixed.
- Remaining medium/low findings are tracked in `reports/review_log.md`.

## 15. Quality Pipeline

The local pipeline is the normal gate before committing implementation changes.

`scripts/check_all.sh` should run:

- Tool availability checks.
- C/C++ formatting check.
- C/C++ linting.
- Static analysis.
- Firmware build.
- Unit tests.
- Python formatting, linting, and tests for tools.
- Web asset validation and packaging.
- Model conversion checks when model files exist.
- Secret scan.
- Firmware size and partition budget checks.

Warnings should be treated as defects. If a warning cannot be fixed immediately, document the reason and scope it tightly.

## 16. Review Loop

Run review cycles periodically and record findings in `reports/review_log.md`.

Finding format:

```text
## YYYY-MM-DD Review

### High
- [ ] file:line - Finding, impact, and required fix.

### Medium
- [ ] file:line - Finding, impact, and proposed fix.

### Low
- [ ] file:line - Finding and cleanup path.
```

Rules:

- Fix high-severity findings immediately.
- Schedule medium findings into the nearest fitting phase.
- Keep low findings visible, but do not let them interrupt critical path work.

## 17. Milestone Order

1. Repository foundation.
2. Camera feasibility.
3. Dataset and recognition evaluation.
4. Storage module.
5. API module.
6. Dashboard.
7. Periodic end-to-end operation.
8. Deep sleep and power tuning.
9. Long-run hardening.
10. Release candidate.

This order avoids optimizing model, UI, or power behavior before the camera and recognition problem is proven with real images.

## 18. Release Criteria

The first useful release is ready when:

- Firmware builds reproducibly from a clean checkout.
- Version is SemVer and sourced from `VERSION`.
- ESP32-CAM captures stable thermometer images.
- Recognition meets measured acceptance criteria or explicitly reports failure.
- One reading is attempted per minute.
- Readings and failures are stored in a bounded ring buffer.
- Dashboard displays current and historical data locally.
- `/api/v1/current`, `/api/v1/readings`, and `/api/v1/status` work.
- The system runs unattended for at least 24 hours.
- Local quality pipeline passes.
- Public interfaces are documented.
- GPLv3 license is present.

## 19. Immediate Next Commit Sequence

Suggested next steps:

1. Add GPLv3 `LICENSE`, `.gitignore`, and `VERSION`.
2. Add firmware skeleton and pinned SDK/build setup.
3. Add `scripts/check_all.sh`.
4. Add camera capture prototype.
5. Add dataset collection script.
6. Add classical recognition evaluation tooling.

Each commit should be small, signed off, conventional, and update the version according to the project rule.
