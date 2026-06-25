## data from several conversations

* make it GPLv3
* prepare a gitignore
* never mention the use of ai or claude code for commit message; make them with conventional commit message format. and details.
* sign off all the commits.
* use semver. single source of truth. we start with 0.0.0. increase by one with each commit. unless said so. single source of truth.
* test coverage 90% percent as goal; add linters and formatters (clang format with google cpp guideline as 120 char per line max and 4 spaces for intendation?), add doxygen and make sure all the interfaces are documented, robust code, etc.
* do from time to time review cycles. mark downt he findings and rate them with severity high, medium, low. fix the high ones immediately. others when fitting.
* do loops until everything is developed.
* take info about hardware from /home/mpetrick/repos/esp32Collection/esp32cam/ - same esp32cam-type; not attached yet (work around that), will do later; make it buildable and with localpipeline-script (see other repo). fix all build warnings, always.
* use the espressif sdk - most recent version
* pin used dependencies - most recent and stable releases: allowed are helper scripts with python, not just c/c++ for the esp32cam. and shell script
* plan first, then implement. do loops.

----------------

````markdown
# ESP32-CAM Local Temperature Readout System — Software Development Plan

## 1. Software Vision

The project is a fully local, self-hosted ESP32-CAM system that periodically wakes up, captures an image of a fixed-position digital thermometer, extracts the displayed temperature value on-device, stores readings locally, and serves both a modern web interface and raw API endpoints directly from the ESP32.

The system should require no cloud dependency during normal operation. It should be robust, deterministic, inspectable, and maintainable. The firmware should be written in C/C++ for the ESP32 platform, with a separate local development pipeline for model training, conversion, firmware build, linting, static analysis, tests, packaging, and deployment.

The target behavior is:

1. Wake up once per minute using real wall-clock timing as closely as feasible.
2. Capture one image from the ESP32-CAM.
3. Preprocess the image on-device.
4. Run a lightweight recognition pipeline to read the thermometer value.
5. Validate and store the reading with timestamp and quality metadata.
6. Return to low-power mode where applicable.
7. Serve a local HTML dashboard from the ESP32.
8. Expose REST-like API endpoints for raw data access.
9. Use bounded local storage, preferably a ring buffer that overwrites the oldest readings when the memory budget is reached.

---

## 2. Core Requirements

### 2.1 Hardware Target

Primary target:

- ESP32-CAM class device
- Camera module supported by the ESP32 camera driver
- Onboard flash storage
- Optional PSRAM strongly preferred
- Wi-Fi enabled
- Fixed camera-to-display distance
- Stable mounting
- Controlled lighting
- Digital thermometer with repeatable display geometry

Degrees of freedom:

- Exact ESP32-CAM board variant
- Exact camera resolution
- Whether PSRAM is mandatory or optional
- Whether the device is continuously powered or battery powered
- Whether deep sleep is required in the first version or deferred

Recommendation:

- Use an ESP32-CAM module with PSRAM.
- Use external stable power for early development.
- Add deep-sleep optimization after the core image recognition and storage pipeline works.

---

### 2.2 Periodic Operation

The system shall take one measurement approximately once per minute.

Nominal cycle:

1. Wake up.
2. Initialize camera.
3. Synchronize or recover time.
4. Capture image.
5. Crop/preprocess relevant region.
6. Run recognition algorithm.
7. Validate reading.
8. Persist reading.
9. Serve or update local data state.
10. Return to sleep or idle.

Requirements:

- Measurement cadence: one reading per minute.
- Real wall-clock timing should be maintained as well as possible.
- If the device is asleep, wake-up should use ESP32 timer wake-up.
- If the device remains powered and awake, use a scheduler loop with drift correction.
- Missed or failed readings must be recorded as failed samples, not silently ignored.
- Each reading should include a timestamp, value, and status metadata.

Reading record example:

```json
{
  "timestamp": 1750000000,
  "temperature_c": 21.7,
  "status": "ok",
  "confidence": 0.94,
  "source": "ml_v1",
  "error": null
}
````

Failure record example:

```json
{
  "timestamp": 1750000060,
  "temperature_c": null,
  "status": "recognition_failed",
  "confidence": 0.31,
  "source": "ml_v1",
  "error": "digit_confidence_below_threshold"
}
```

---

## 3. Image Recognition Strategy

### 3.1 Recognition Goal

The ESP32-CAM must recognize the value shown on a digital thermometer from a single captured image.

The environment is controlled:

* Fixed distance
* Fixed angle
* Stable illumination
* Known display position
* Known display type
* Repeatable camera settings

This makes the problem significantly easier than general OCR.

---

### 3.2 Candidate Recognition Approaches

The implementation may choose between several approaches depending on empirical reliability.

#### Option A: Classical Computer Vision

Possible techniques:

* Crop fixed region of interest
* Convert to grayscale
* Threshold image
* Segment digits
* Recognize seven-segment digits using rule-based geometry
* Detect decimal point and sign
* Validate result using known thermometer format

Advantages:

* Very small memory footprint
* Fast
* Explainable
* No model training required or minimal calibration only
* Highly suitable for seven-segment displays

Disadvantages:

* Sensitive to display style, glare, shadows, or unexpected distortions
* Requires carefully engineered preprocessing

Recommended when:

* The thermometer uses a standard seven-segment LCD display.
* Lighting and camera position are stable.
* The display has high contrast.

#### Option B: TinyML Digit Classifier

Possible techniques:

* Train a small model on cropped digit images
* Use TensorFlow Lite for Microcontrollers, Edge Impulse, or similar tooling
* Classify individual digit regions
* Postprocess digit sequence into a temperature value

Advantages:

* More tolerant of visual variation than simple rules
* Compact if classifying small cropped digits
* Feasible on ESP32 with quantized int8 model

Disadvantages:

* Requires dataset collection and labeling
* Requires model conversion and firmware integration
* More difficult to debug than classical logic

Recommended when:

* The digit shapes are not clean enough for rule-based recognition.
* There are moderate variations in lighting or LCD contrast.
* The model can be kept small.

#### Option C: Hybrid Pipeline

Recommended default.

Use classical image processing for:

* Cropping
* Perspective normalization, if needed
* Thresholding
* Digit segmentation
* Decimal point detection
* Sanity checks

Use TinyML only for:

* Per-digit classification
* Ambiguous digit resolution
* Quality estimation

Advantages:

* Reduces neural network size
* Improves explainability
* Improves robustness
* Keeps inference feasible on ESP32

---

### 3.3 Model Constraints

If a neural model is used:

* It must be small enough for ESP32 RAM and flash limits.
* Prefer int8 quantization.
* Prefer per-digit classification over full-image OCR.
* Avoid large generic OCR models.
* Avoid LLM-style models.
* Use TensorFlow Lite for Microcontrollers, Edge Impulse export, or another embedded-friendly inference runtime.

Expected model type:

* Input: small grayscale crop, for example 16x24, 20x32, or 28x28 pixels
* Output: digit class 0-9 plus optional blank/error class
* Quantization: int8
* Model size target: ideally below 100 KB, acceptable up to a few hundred KB if memory allows

---

## 4. Data Collection and Training Workflow

### 4.1 Capture Dataset

A local toolchain should support collecting images from the real ESP32-CAM setup.

Dataset requirements:

* Same physical camera position as final deployment
* Same lighting conditions as final deployment
* Same camera settings as final deployment where possible
* Multiple temperature values
* Multiple captures per value
* Include edge cases:

  * Decimal point visible
  * Negative values, if possible
  * Bright conditions
  * Slightly dim conditions
  * Low-contrast LCD
  * Glare or partial reflection
  * Failed/invalid images

Dataset layout example:

```text
dataset/
  raw/
    2026-06-23_120000.jpg
    2026-06-23_120100.jpg
  labeled/
    images.csv
  crops/
    digit_0/
    digit_1/
    digit_2/
    ...
    digit_9/
    blank/
    invalid/
```

Example `images.csv`:

```csv
filename,timestamp,label_temperature,display_text,quality,notes
2026-06-23_120000.jpg,1750000000,21.7,21.7,good,baseline
2026-06-23_120100.jpg,1750000060,21.8,21.8,good,baseline
```

---

### 4.2 Training Pipeline

The repository shall include scripts for:

* Importing raw images
* Cropping region of interest
* Generating digit crops
* Labeling or assisting labeling
* Training the model
* Evaluating the model
* Quantizing the model
* Exporting a C/C++ compatible model artifact
* Producing a versioned firmware include file

Possible tooling:

* Python
* TensorFlow / Keras
* TensorFlow Lite
* TensorFlow Lite for Microcontrollers
* Edge Impulse
* OpenCV for preprocessing and dataset generation

Required outputs:

```text
models/
  thermometer_digit_model.tflite
  thermometer_digit_model_int8.tflite
firmware/src/model_data.cc
firmware/include/model_data.h
reports/model_eval.md
reports/confusion_matrix.csv
```

---

### 4.3 Model Evaluation Requirements

Before deployment, the model or recognition pipeline must be evaluated.

Minimum metrics:

* Per-digit accuracy
* Full-reading accuracy
* Confusion matrix
* Confidence distribution
* Failure rate
* Invalid-image rejection behavior

Acceptance criteria proposal:

* Per-digit accuracy: >= 99% on validation set under controlled conditions
* Full-reading accuracy: >= 98% on validation set
* Unknown/invalid rejection: explicit failure instead of false confident reading
* No silent numeric hallucination

These thresholds may be adjusted after real measurements.

---

## 5. Firmware Architecture

### 5.1 Language and Platform

Firmware shall be written in C/C++.

Possible build frameworks:

* PlatformIO
* ESP-IDF
* Arduino framework for ESP32

Recommendation:

* Use PlatformIO for developer ergonomics.
* Use Arduino framework initially if camera/web server libraries are easier.
* Consider ESP-IDF if power management, partitioning, and production robustness become more important.

---

### 5.2 Main Firmware Modules

Proposed structure:

```text
firmware/
  include/
    app_config.h
    camera_manager.h
    image_preprocessor.h
    recognition.h
    storage_ring_buffer.h
    time_manager.h
    web_server.h
    api_server.h
    diagnostics.h
    model_data.h
  src/
    main.cpp
    camera_manager.cpp
    image_preprocessor.cpp
    recognition.cpp
    storage_ring_buffer.cpp
    time_manager.cpp
    web_server.cpp
    api_server.cpp
    diagnostics.cpp
    model_data.cc
  test/
    test_ring_buffer.cpp
    test_record_encoding.cpp
    test_value_validation.cpp
```

---

### 5.3 Firmware Components

#### Camera Manager

Responsibilities:

* Initialize camera
* Apply fixed camera settings
* Capture frame
* Handle capture failures
* Release frame buffer
* Optionally store debug captures during development

Configurable parameters:

* Resolution
* Pixel format
* Exposure
* Gain
* White balance
* Brightness
* Contrast
* Region of interest

#### Image Preprocessor

Responsibilities:

* Crop region of interest
* Convert image format if necessary
* Downscale
* Convert to grayscale
* Apply thresholding or normalization
* Segment digits
* Detect decimal point
* Prepare model input tensors if TinyML is used

Requirements:

* Avoid unnecessary heap allocation
* Check all buffer boundaries
* Use fixed-size buffers where practical
* Return explicit error states

#### Recognition Engine

Responsibilities:

* Recognize displayed temperature value
* Provide confidence score
* Provide intermediate diagnostics
* Reject uncertain readings

Possible implementation paths:

* Rule-based seven-segment decoder
* TinyML digit classifier
* Hybrid decoder

Output structure:

```cpp
struct RecognitionResult {
    bool ok;
    float value_celsius;
    float confidence;
    const char* status;
    const char* error;
};
```

Validation logic:

* Reject impossible digit count
* Reject impossible decimal placement
* Reject low-confidence digits
* Reject values outside configured physical range
* Optionally compare with previous reading and flag unrealistic jumps

#### Time Manager

Responsibilities:

* Maintain timestamps
* Use NTP if Wi-Fi is available
* Fall back to RTC/deep-sleep timer progression if NTP is unavailable
* Track time validity

Requirements:

* Store whether timestamp is synchronized or estimated
* Avoid corrupting historical data if time is unavailable
* Optionally expose time status through API

#### Storage Ring Buffer

Responsibilities:

* Persist temperature readings locally
* Use bounded memory or flash storage
* Overwrite oldest records when capacity is reached
* Survive reboot
* Avoid excessive flash wear where feasible

Possible storage backends:

* LittleFS
* SPIFFS
* Preferences/NVS for metadata
* Raw flash partition for fixed-size records

Recommendation:

* Use a fixed-size binary ring buffer in a dedicated file or partition.
* Store metadata separately.
* Prefer compact binary records over JSON for internal storage.
* Generate JSON only for API responses.

Record design example:

```cpp
struct ReadingRecord {
    uint32_t timestamp;
    int16_t temperature_centi_c;
    uint8_t status;
    uint8_t confidence_percent;
    uint16_t flags;
};
```

Approximate storage:

* 10 bytes per reading is feasible.
* One reading per minute = 1,440 readings per day.
* 1 MB storage could hold roughly 100,000 compact records.
* 100,000 records at one per minute is about 69 days.

Actual storage capacity depends on metadata, filesystem overhead, flash partitioning, and record format.

#### Web Server

Responsibilities:

* Serve local dashboard
* Serve static HTML/CSS/JS assets
* Serve chart data
* Serve status and diagnostics
* Support light/dark theme switching
* Provide modern responsive UI

Possible implementation:

* ESPAsyncWebServer
* Native ESP-IDF HTTP server
* Arduino WebServer for simpler implementation

Web UI requirements:

* Modern dashboard
* Current temperature card
* Historical chart
* Light mode and dark mode
* Color theme selection
* Responsive layout for desktop and mobile
* Local-only operation
* No mandatory CDN dependency
* Client-side chart rendering
* Optionally compressed static assets

Frontend degrees of freedom:

* Vanilla JavaScript
* Minimal charting library served locally
* Custom canvas/SVG chart renderer
* Chart.js bundled locally if size permits

Recommendation:

* Avoid external CDN dependencies.
* Start with lightweight vanilla JavaScript and `<canvas>`.
* Add a local chart library only if needed.

#### REST API Server

The device shall expose REST-like endpoints for raw data access.

Proposed endpoints:

```text
GET /api/v1/status
GET /api/v1/current
GET /api/v1/readings
GET /api/v1/readings?from=1750000000&to=1750086400
GET /api/v1/readings?limit=1440
GET /api/v1/readings/latest?count=60
GET /api/v1/config
POST /api/v1/config
GET /api/v1/diagnostics
POST /api/v1/capture
```

Endpoint behavior:

##### `GET /api/v1/status`

Returns device state.

```json
{
  "device": "esp32-cam-thermometer",
  "firmware_version": "0.1.0",
  "uptime_s": 12345,
  "time_synced": true,
  "storage_used_bytes": 123456,
  "storage_capacity_bytes": 1048576,
  "readings_count": 1440,
  "last_reading_status": "ok",
  "wifi_rssi": -61
}
```

##### `GET /api/v1/current`

Returns the latest reading.

```json
{
  "timestamp": 1750000000,
  "temperature_c": 21.7,
  "status": "ok",
  "confidence": 0.94
}
```

##### `GET /api/v1/readings`

Returns historical readings.

Query parameters:

* `from`: Unix timestamp
* `to`: Unix timestamp
* `limit`: maximum number of records
* `format`: `json` or compact format if later implemented

##### `POST /api/v1/config`

Allows controlled configuration changes.

Possible settings:

* Measurement interval
* Display range limits
* Timezone offset
* Theme default
* Camera parameters
* Recognition thresholds

Security note:

* Configuration writes should be protected if the network is not fully trusted.

---

## 6. Local Web Interface

### 6.1 UI Vision

The local dashboard should feel modern and polished despite running from an ESP32.

UI elements:

* Current temperature display
* Last update timestamp
* Recognition confidence
* Status badge
* Historical chart
* Time range selector:

  * Last hour
  * Last 6 hours
  * Last 24 hours
  * Last 7 days
  * Custom range if feasible
* Light/dark mode toggle
* Color theme selection
* Device status panel
* Diagnostics panel
* Optional raw data download

### 6.2 Frontend Constraints

The ESP32 has limited flash, RAM, and CPU resources.

Frontend requirements:

* Minimize asset size
* Avoid heavy frameworks
* Avoid external dependencies
* Bundle static assets locally
* Use gzip-compressed assets if supported
* Render chart client-side in the browser
* Fetch data via REST API

Recommended frontend stack:

* HTML
* CSS custom properties
* Vanilla JavaScript
* Canvas or SVG chart rendering
* Optional small local chart library

---

## 7. Storage Design

### 7.1 Ring Buffer Requirement

The project shall use bounded storage. When the configured storage limit is reached, the oldest readings shall be overwritten.

Requirements:

* Configurable capacity, for example 1 MB
* Fixed-size records preferred
* O(1) append
* Efficient sequential read
* Persistent head/tail metadata
* Corruption detection where feasible
* Recovery behavior after power loss

### 7.2 Record Fields

Minimum:

* Timestamp
* Temperature value
* Status code
* Confidence
* Flags

Optional:

* Recognition engine version
* Time validity flag
* Battery voltage
* Wi-Fi RSSI
* Capture duration
* Inference duration

### 7.3 Storage Backend Recommendation

Preferred production design:

* Dedicated binary ring-buffer file on LittleFS or raw partition
* Metadata file or NVS keys:

  * write index
  * record count
  * capacity
  * schema version
  * checksum

Simple first implementation:

* LittleFS file with fixed-size binary records
* Separate metadata file
* Rebuild metadata by scanning if metadata is corrupt

---

## 8. Reliability and Robustness

### 8.1 Failure Handling

The firmware must explicitly handle:

* Camera initialization failure
* Capture failure
* Invalid frame
* Preprocessing failure
* Recognition failure
* Low confidence
* Storage write failure
* Filesystem mount failure
* Wi-Fi unavailable
* Time unavailable
* API request malformed
* Out-of-memory condition

No failure should cause silent bad data.

### 8.2 Data Validation

Temperature validation:

* Configurable minimum and maximum allowed temperature
* Reject values outside range
* Optional smoothing or plausibility check
* Flag sudden jumps beyond configured delta

Important:

* Smoothing must not replace raw readings unless clearly marked.
* Store original recognized result or failure state.

### 8.3 Watchdog and Recovery

The system should use:

* Watchdog-friendly loops
* Timeouts for camera capture
* Timeouts for Wi-Fi
* Safe reboot on unrecoverable errors
* Persistent boot counter
* Last error storage

---

## 9. Safety and Security

### 9.1 Local-Only Assumption

The system is intended for local network use.

Still, the firmware should avoid unsafe assumptions:

* Do not expose configuration write endpoints without protection on untrusted networks.
* Avoid buffer overflows.
* Validate all query parameters.
* Limit API response sizes.
* Avoid dynamic memory fragmentation.
* Do not include hardcoded private credentials in source control.

### 9.2 Credentials

Wi-Fi credentials should be handled carefully.

Options:

* Build-time local config file excluded from Git
* Captive portal provisioning
* Serial provisioning
* Encrypted NVS if supported and worth the complexity

Repository should include:

```text
config.example.h
config.local.h
```

`config.local.h` must be ignored by Git.

---

## 10. Build, Test, and Tooling Pipeline

### 10.1 Local Pipeline Script

The repository shall include a single shell script that runs the complete local quality pipeline.

Example:

```text
scripts/check_all.sh
```

Responsibilities:

1. Verify required tools are installed.
2. Format C/C++ code.
3. Run C/C++ linting.
4. Run static analysis.
5. Build firmware.
6. Run unit tests.
7. Check frontend assets.
8. Run Python formatting and linting for ML tools.
9. Run model conversion checks if model files are present.
10. Produce build artifacts.

Example command:

```bash
./scripts/check_all.sh
```

### 10.2 Suggested Tools

C/C++:

* clang-format
* clang-tidy
* cppcheck
* PlatformIO test
* PlatformIO build
* Compiler warnings as errors where practical

Python:

* ruff
* black
* mypy where useful
* pytest

Frontend:

* eslint if JavaScript becomes non-trivial
* prettier if asset pipeline is used
* HTML/CSS validation optional

Security and robustness:

* Check for secrets
* Check binary sizes
* Check partition utilization
* Optional firmware size budget check

### 10.3 Example Pipeline Layout

```text
scripts/
  check_all.sh
  format_cpp.sh
  lint_cpp.sh
  static_analysis.sh
  build_firmware.sh
  test_firmware.sh
  train_model.sh
  convert_model.sh
  package_web_assets.sh
  flash_device.sh
  collect_dataset.sh
```

---

## 11. Repository Structure

```text
esp32-cam-temperature-reader/
  README.md
  DEVELOPMENT_PLAN.md
  LICENSE
  .gitignore
  platformio.ini

  firmware/
    include/
    src/
    test/
    partitions.csv

  web/
    index.html
    styles.css
    app.js
    assets/

  ml/
    dataset/
    notebooks/
    scripts/
    training/
    export/
    requirements.txt

  tools/
    image_capture/
    labeler/
    dataset_tools/

  scripts/
    check_all.sh
    build_firmware.sh
    flash_device.sh
    monitor_serial.sh
    collect_dataset.sh
    train_model.sh
    convert_model.sh

  docs/
    architecture.md
    api.md
    storage.md
    recognition.md
    calibration.md
    troubleshooting.md

  reports/
    model_eval.md
    static_analysis.md
```

---

## 12. Configuration

Configuration should be centralized and versioned.

Example configuration areas:

```cpp
#define MEASUREMENT_INTERVAL_SECONDS 60
#define STORAGE_MAX_BYTES 1048576
#define TEMP_MIN_C -20.0f
#define TEMP_MAX_C 60.0f
#define RECOGNITION_MIN_CONFIDENCE 0.85f
#define CAMERA_FRAME_SIZE FRAMESIZE_QVGA
#define ROI_X 40
#define ROI_Y 80
#define ROI_W 240
#define ROI_H 80
```

Runtime-configurable settings may be exposed through the web UI or API later.

---

## 13. API Specification Draft

### 13.1 Status Codes

Recognition status values:

```text
ok
camera_failed
image_invalid
preprocess_failed
recognition_failed
confidence_too_low
value_out_of_range
storage_failed
time_unknown
```

### 13.2 API Versioning

All endpoints should use a versioned prefix:

```text
/api/v1/
```

Future breaking changes should use:

```text
/api/v2/
```

### 13.3 API Response Rules

Requirements:

* JSON responses must be valid.
* Large responses must support limits.
* Invalid parameters must return clear errors.
* API should never block measurement for too long.
* Historical data should be returned in chronological order by default.

Error example:

```json
{
  "error": {
    "code": "invalid_parameter",
    "message": "Parameter 'limit' must be between 1 and 10000."
  }
}
```

---

## 14. Development Milestones

### Milestone 0: Feasibility Prototype

Goal:

* Prove ESP32-CAM can capture readable thermometer images.

Tasks:

* Configure camera.
* Capture image.
* Serve latest image or download over serial/Wi-Fi.
* Fix mounting and lighting.
* Select resolution and exposure.

Deliverables:

* Sample image dataset.
* Initial camera settings.
* Documented region of interest.

### Milestone 1: Classical Recognition Prototype

Goal:

* Test whether rule-based recognition is sufficient.

Tasks:

* Crop ROI.
* Threshold image.
* Segment digits.
* Decode seven-segment digits.
* Validate decimal point.
* Compare against manual labels.

Deliverables:

* Recognition accuracy report.
* Decision whether TinyML is necessary.

### Milestone 2: TinyML Prototype

Goal:

* Train and deploy compact digit classifier if needed.

Tasks:

* Create labeled digit dataset.
* Train small classifier.
* Quantize to int8.
* Convert to C array.
* Run inference on ESP32.
* Measure RAM, flash, and runtime.

Deliverables:

* Model artifact.
* Firmware integration.
* Evaluation report.

### Milestone 3: Persistent Storage

Goal:

* Store readings in bounded local ring buffer.

Tasks:

* Implement fixed-size record format.
* Implement append and historical read.
* Implement metadata persistence.
* Handle wraparound.
* Test corruption recovery.

Deliverables:

* Storage module.
* Unit tests.
* Storage capacity calculation.

### Milestone 4: Web UI and API

Goal:

* Provide local dashboard and raw API.

Tasks:

* Implement `/api/v1/current`.
* Implement `/api/v1/readings`.
* Implement `/api/v1/status`.
* Build modern HTML dashboard.
* Add chart rendering.
* Add light/dark mode.
* Add theme selection.

Deliverables:

* Local dashboard.
* API documentation.
* Browser-tested chart.

### Milestone 5: Full Periodic Operation

Goal:

* Run complete one-minute measurement loop.

Tasks:

* Add scheduler or deep sleep.
* Add time management.
* Integrate capture, recognition, storage, and serving.
* Add failure recording.
* Add diagnostics.

Deliverables:

* End-to-end working system.
* 24-hour stability test.

### Milestone 6: Robustness and Polish

Goal:

* Make the project maintainable and reliable.

Tasks:

* Add linters.
* Add static analysis.
* Add CI-compatible local pipeline.
* Add documentation.
* Add configuration examples.
* Optimize memory usage.
* Test power recovery.
* Test Wi-Fi loss.
* Test bad image conditions.

Deliverables:

* `scripts/check_all.sh`
* Final documentation
* Stable firmware image

---

## 15. Testing Strategy

### 15.1 Unit Tests

Test modules:

* Ring buffer wraparound
* Record encoding/decoding
* Timestamp handling
* API parameter validation
* Temperature plausibility validation
* Recognition postprocessing

### 15.2 Integration Tests

Test flows:

* Capture image and recognize value
* Store reading and fetch through API
* Fill ring buffer and verify overwrite
* Simulate failed recognition
* Simulate storage failure
* Simulate Wi-Fi reconnect

### 15.3 Long-Run Tests

Minimum recommended tests:

* 24-hour continuous test
* Multi-day storage wraparound test
* Power-loss recovery test
* Wi-Fi outage test
* Lighting variation test

---

## 16. Performance Budgets

Initial target budgets:

* Measurement interval: 60 seconds
* Image capture: below 5 seconds preferred
* Recognition: below 30 seconds acceptable, below 5 seconds preferred
* Storage write: below 1 second
* API current response: below 500 ms
* API historical response: bounded by limit
* Internal reading storage: approximately 1 MB target
* Web assets: keep small enough for ESP32 flash partition

Important:

* The system does not require real-time image recognition.
* A recognition time up to one minute may be acceptable only if it does not break the next scheduled measurement.
* Prefer finishing well below 60 seconds to leave margin.

---

## 17. Open Design Decisions

These are intentionally left flexible for implementation choices:

1. Rule-based recognition vs TinyML vs hybrid.
2. ESP-IDF vs Arduino framework vs PlatformIO abstraction.
3. LittleFS vs raw partition for ring buffer.
4. Deep sleep from the first version vs always-on prototype.
5. Exact frontend chart implementation.
6. Exact model architecture.
7. Exact camera resolution and preprocessing dimensions.
8. Whether API writes require authentication in the first version.
9. Whether timestamps use UTC only or include local timezone rendering.
10. Whether failed readings are shown in the chart or hidden by default.

Recommended default choices:

* PlatformIO + Arduino framework for first prototype.
* Hybrid recognition pipeline.
* LittleFS fixed-record ring buffer.
* UTC timestamps internally.
* Browser renders local timezone.
* Vanilla JavaScript dashboard.
* Local-only static assets.
* Failed readings stored and visible in diagnostics.

---

## 18. Acceptance Criteria

The project is considered successful when:

1. ESP32-CAM captures stable images of the thermometer.
2. The system reads the displayed temperature reliably under controlled conditions.
3. One reading is attempted every minute.
4. Readings are stored locally with timestamps.
5. Storage is bounded and overwrites oldest records through a ring buffer.
6. A local web dashboard displays current and historical temperature.
7. User can switch between light and dark mode.
8. User can select at least one additional color theme.
9. REST API exposes current and historical readings.
10. Failed readings are represented explicitly.
11. The local development pipeline builds, lints, analyzes, and tests the project.
12. The firmware runs for at least 24 hours without manual intervention.
13. The codebase avoids unsafe buffer handling and validates external inputs.

---

## 19. Immediate Next Steps

1. Select exact ESP32-CAM board.
2. Confirm PSRAM availability.
3. Capture first fixed-position thermometer images.
4. Decide initial camera resolution and ROI.
5. Build a simple firmware that captures and serves one image.
6. Create dataset folder structure.
7. Prototype classical seven-segment recognition on desktop.
8. Decide whether TinyML is necessary.
9. Implement first ring-buffer storage prototype.
10. Create first version of local web dashboard and API.

---

## 20. Non-Goals for Initial Version

The first version should not attempt:

* General OCR
* Arbitrary thermometer layouts
* Cloud synchronization
* Mobile app development
* Complex user accounts
* Heavy frontend frameworks
* Large neural models
* Real-time video processing
* Multi-camera support

These can be considered later only if the core system is reliable.

---

## 21. Guiding Principles

* Prefer simple deterministic logic where it works.
* Use TinyML only where it improves reliability.
* Store raw facts and explicit failure states.
* Keep storage bounded.
* Keep the web interface local and lightweight.
* Validate everything crossing an API boundary.
* Avoid silent failures.
* Make the development pipeline reproducible.
* Optimize only after measuring.
* Design for field debugging from the beginning.

```
```


----------------


idea for a esp32 cam project.

ChatGPT

Great project. I’d frame it as ESP32-CAM visual sensor logger + OCR + local web dashboard + REST API.
Core architecture

Hardware

    ESP32-CAM module

    Fixed-position camera mount

    Target display/sensor screen with stable lighting

    Optional: small LED illumination to keep OCR reliable

    microSD card if you want more history than ESP32 flash can safely hold

Data flow

    Every minute

        ESP32-CAM takes a snapshot.

        Crop image to predefined regions of interest: temperature, humidity, etc.

        Run OCR or visual digit recognition.

        Validate parsed values.

        Store timestamped readings in a circular buffer.

    Storage

        RAM circular buffer for recent data.

        Optional persistent storage:

            LittleFS/SPIFFS for small amounts.

            microSD for multi-day history.

        Suggested sample schema:

{
  "ts": "2026-06-25T14:32:00Z",
  "temperature": 23.4,
  "humidity": 48.0,
  "confidence": 0.91
}

    Web server

        ESP32 serves a local dashboard.

        Shows:

            current temperature/humidity

            last 24h graph

            optional transparent overlays for last 3 days

            camera snapshot preview

            OCR confidence/status

    REST API

        GET /api/latest

        GET /api/readings

        GET /api/readings?date=260625

        GET /api/readings?from=2026-06-24T00:00:00Z&to=2026-06-25T00:00:00Z

        GET /api/status

        POST /api/config

Important design decision

Running full OCR directly on an ESP32-CAM is hard. A better first version is:

Option A — simple and robust

    Use fixed camera position.

    Crop fixed digit regions.

    Use template matching or a tiny ML model for seven-segment/LCD digits.

    Much easier than general OCR.

Option B — more flexible

    ESP32 captures images.

    ESP32 sends image to another local server for OCR.

    Server returns values.

    ESP32 stores/serves the data.

Option C — hybrid

    ESP32 does simple recognition locally.

    Web UI allows manual correction/calibration.

Circular buffer design

At 1 sample/minute:

    1 day = 1,440 samples

    3 days = 4,320 samples

    7 days = 10,080 samples

Example C-style record:

struct Reading {
  uint32_t timestamp;
  float temperature;
  float humidity;
  uint8_t confidence;
};

Approx. 16 bytes per reading:

    1 day ≈ 23 KB

    7 days ≈ 161 KB

So RAM may work for 1–3 days, but persistent storage is safer.
Web dashboard idea

Use the ESP32 to serve:

    static index.html

    Chart.js from local file or CDN

    JSON fetched from /api/readings

The chart can render:

    current day as solid line

    previous days as transparent lines

    fixed Y-axis from 0–40 °C

Recommended MVP

    ESP32-CAM connects to Wi-Fi.

    Serves /snapshot.

    Takes one image per minute.

    Stores fake/random temperature data first.

    Serves /api/latest and /api/readings.

    Build dashboard graph.

    Add cropping.

    Add digit recognition/OCR.

    Add calibration UI.

    Add persistent storage.

Risks

The biggest risks are:

    unstable lighting

    camera movement

    blurry images

    reflective LCD/display

    OCR errors

    ESP32 memory limits

So the mechanical setup matters almost as much as the code. A fixed enclosure with controlled lighting will make this project much easier.

find funny ideas for a geeky repository name.

Here are some geeky repository-name ideas for the ESP32 camera/OCR environmental logger:
Strong fits

    thermo-vision

    sensor-scryer

    climate-cam

    ocracle

    gauge-gazer

    read-my-dials

    pixel-thermometer

    enviro-eyes

    scope-and-sensor

    screen-scraper-32

    camperature

    tempest32

    humid-eye

    display-diviner

    metric-mirror

More playful

    the-therminal

    fahrenheit-451-not-found

    heat-seek-and-destroy

    degree-of-freedom

    ctrl-alt-deg

    the-great-gatsbyte

    temperature-unknown

    cloudy-with-a-chance-of-sensors

    wifi-watcher

    one-minute-monitor

    dataloggernaut

    cam-ometer

    eye-spy-iot

    ocr-and-order

    the-reading-rainbow

ESP32-specific

    esp-eye-see-you

    espionage-32

    esp32-vision-quest

    esp-cam-and-carry-on

    cam32

    esp-ocr-press-o

    pixel-pirate-32

    the-espionage-cam

My shortlist

    ocracle — OCR + oracle; compact and memorable.

    camperature — camera + temperature; immediately descriptive.

    gauge-gazer — excellent if it reads physical displays.

    esp-eye-see-you — deliberately silly, ESP32-specific.

    the-therminal — terminal + thermal sensor.

    ocr-and-order — ideal if the project is more playful than formal.

    sensor-scryer — fits the “camera interpreting instruments” concept.

For a public repository, I would choose ocracle if the OCR aspect is central, or gauge-gazer if the device may later read more than temperature and humidity.

ten ideas. make esp32 part of it. and temperure. hot weather or so.

    esp32-hotshot

    esp32-heatwave

    esp32-tempest

    esp32-thermo-vision

    esp32-sunburn

    esp32-fever-dream

    esp32-heat-seeker

    esp32-hot-pixels

    esp32-degree-of-freedom

    esp32-too-darn-hot



    
-------------

