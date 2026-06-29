# ESP32-CAM App And Training Architecture

This document describes the current end-to-end prototype: ESP32-CAM capture,
on-device TinyML digit recognition, local storage, HTTP API output, and the host
training loop.

## Current Prototype State

- Device hostname: `esp32-fever-dream`.
- Browser/API base URL: `http://esp32-fever-dream`.
- A mounted reading was validated during deployment (`29.00 C`, `41%`), but the
  final post-flash check ended in `confidence_too_low`; OCR is integrated but
  not stable yet.
- The current data model and API are five-value AQS records: CO2, HCHO, TVOC,
  temperature, and humidity.
- Recognition interval: one automatic sample every 10 seconds after boot.
- The TFLite model is an int8 digit classifier embedded as
  `firmware/generated/digit_classifier_model.h`.
- The mounted prototype includes temporary corrections for observed
  mounted-display misreads around `29C / 41%` and `27C / 41%`.
- The mounted prototype confidence threshold is currently relaxed to 30%.
- The model is useful for integration testing. It is not production-ready across
  the current mounted setup, arbitrary camera shifts, display values, or bad
  lighting.

## C4 Context

```mermaid
C4Context
    title System Context
    Person(user, "Local user", "Views recent readings in a browser")
    System(device, "ESP32 Fever Dream", "ESP32-CAM firmware, camera capture, TinyML OCR, local API")
    System_Ext(display, "Air quality sensor (AQS)", "Fixed screen showing CO2, HCHO, TVOC, temperature, and humidity")
    System_Ext(workstation, "Developer workstation", "Dataset capture, labeling, training, flashing")

    Rel(user, device, "Reads dashboard/API over Wi-Fi")
    Rel(device, display, "Captures 640x480 JPEG frames")
    Rel(workstation, device, "Captures datasets over Wi-Fi or USB serial, flashes firmware, queries API")
```

## Containers

```mermaid
flowchart TB
    user(["Local user"])

    subgraph device["ESP32 Fever Dream"]
        firmware["ESP32 firmware\n(C++ / ESP-IDF)\nWi-Fi, camera, measurement loop, TFLite OCR"]
        api["HTTP API\n(esp_http_server)\nhealth · capture · status · readings"]
        serial["USB serial fallback\n(UART)\ndataset capture without Wi-Fi"]
        web["Embedded dashboard\n(HTML/CSS/JS in flash)\nserved directly by ESP32"]
        storage["Reading ring buffer\n(RAM)\nlast 1 440 records"]
    end

    training["Training pipeline\n(Python / TensorFlow)\nbuilds int8 digit model header"]
    workstation(["Developer workstation"])

    user -->|views| web
    web -->|"GET /api/v1/*"| api
    firmware --> storage
    api --> storage
    training -->|"exports digit_classifier_model.h"| firmware
    workstation -->|"CAPTURE_JPEG"| serial
```

## Firmware Components

```mermaid
flowchart LR
    Boot[app_main] --> Wifi[Wi-Fi station]
    Boot --> Camera[CameraManager]
    Boot --> Server[debug/API HTTP server]
    Boot --> Serial[USB serial capture task]
    Boot --> Task[Measurement task]

    Task --> Capture[1. Capture image]
    Capture --> Decode[2. Decode JPEG to RGB888]
    Decode --> Locate[3. Locate and orient display]
    Locate --> OCR[4. Run TFLite digit OCR]
    OCR --> Validate[5. Validate and save]
    Validate --> Buffer[StorageRingBuffer]
    Task -. pipeline stage and cycle .-> API[Status API]
    API -. 400 ms status polling .-> Web[Embedded dashboard]
    Server --> Router[ApiRouter]
    Serial --> Capture
    Router --> Buffer
    Router --> Json[ApiSerializer]
```

## Training Flow

```mermaid
flowchart TD
    A[ESP32 /debug/capture.jpg] --> B[Capture batch under tools/dataset/captures]
    B --> C[Human confirmed labels_environment.csv]
    C --> D[Fixed ROI digit crop builder]
    E[Synthetic digit augmentation] --> D
    D --> F[digit_labels.csv]
    F --> G[TensorFlow tiny CNN]
    G --> H[Int8 TFLite export]
    H --> I[firmware/generated/digit_classifier_model.h]
    I --> J[ESP-IDF build]
    J --> K[Flash ESP32-CAM]
    K --> L[Browser/API validation]
```

## Runtime Sequence

```mermaid
sequenceDiagram
    participant ESP as ESP32-CAM
    participant WiFi as Wi-Fi AP
    participant Display as Air quality display
    participant Browser as Local browser

    ESP->>WiFi: Connect as station
    ESP->>ESP: Start HTTP server
    loop every minute
        ESP->>Display: Capture 640x480 JPEG
        ESP->>ESP: Decode, crop fixed AQS digit ROIs
        ESP->>ESP: Run TFLite Micro classifier
        ESP->>ESP: Validate and store reading
    end
    Browser->>ESP: GET /api/v1/current
    ESP-->>Browser: co2_ppm, hcho, tvoc, temperature_c, humidity_percent, status, confidence
    Browser->>ESP: GET /api/v1/readings/latest?count=1440
    ESP-->>Browser: recent reading records
```

## Acceptance Notes

The current deployment is a working mounted prototype, not a finished OCR
product. Production acceptance needs:

- More real labels covering all digits in both temperature and humidity fields.
- Firmware-side crop debug output or telemetry so host and device preprocessing
  can be compared byte-for-byte.
- Removal of the temporary mounted-display corrections.
- Restoration of a stricter recognition threshold after real validation.
- Held-out real-frame validation across daylight, dim light, glare, and small
  camera shifts.
