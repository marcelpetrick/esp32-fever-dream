# ESP32 Fever Dream

Local ESP32-CAM thermometer readout firmware. The target device captures a fixed-position digital thermometer once per minute, recognizes the displayed temperature, stores readings in bounded local storage, and serves a dashboard plus raw API endpoints directly from the ESP32.

**Status: implementation bootstrap.** Host-side core modules, tests, static web UI, firmware skeleton, ESP-IDF firmware build, debug image capture endpoint, pipeline scripts, GPLv3 license, and SemVer source of truth are present. Persistent flash storage, production HTTP handlers, OCR training data, and the full one-minute device loop are still in progress.

## Current Web UI

The static dashboard lives in `web/` and is designed to be served locally by the ESP32.

It expects:

```text
GET /api/v1/status
GET /api/v1/current
GET /api/v1/readings/latest?count=1440
```

It renders the current reading, device diagnostics, API state, theme controls, and a canvas history chart. No external CDN or internet dependency is used.

## Hardware

Target hardware is borrowed from the existing ESP32-CAM notes in `/home/mpetrick/repos/esp32Collection/esp32cam/`.

| Component | Details |
| --- | --- |
| Module | AI-Thinker ESP32-CAM |
| Programmer | ESP32-CAM-MB with CH340 USB-serial |
| Camera | OV2640 ribbon camera |
| Chip | ESP32-D0WDQ6 rev 1.0, dual core, 240 MHz |
| Flash | 4 MB Winbond, 3.3 V |
| Serial port | `/dev/ttyUSB0` |

The firmware configuration includes the AI-Thinker camera pin map and assumes PSRAM is available.

## Toolchain

Firmware target:

- ESP-IDF v6.0.1.
- ESP32 target.
- C++ firmware core with ESP-IDF app entrypoint.
- Managed component: `espressif/esp32-camera` pinned to `2.1.7`.

Host/local checks:

- CMake and Ninja.
- clang-format.
- clang-tidy.
- cppcheck.
- Doxygen.
- shellcheck.
- Node.js for JavaScript syntax checks.
- Python 3 plus ruff and black for tooling checks.

## Local Pipeline

```bash
./scripts/check_all.sh
```

Stages:

1. clang-format check.
2. Host CMake configure.
3. Host C++ build.
4. Host unit tests.
5. shellcheck, cppcheck, and clang-tidy when available.
6. ESP-IDF firmware build for `esp32`.
7. Static web asset syntax check.
8. Python compile, ruff, and black checks when available.
9. Doxygen generation with warnings treated as errors.

The pipeline is intended to run without attached hardware. It builds the firmware image locally but does not flash the board.

## Build Firmware

ESP-IDF is not vendored. The scripts source the pinned local install automatically when `idf.py` is not already on `PATH`:

```bash
./scripts/build_firmware.sh
```

Default local install path:

```text
~/.local/opt/esp-idf-v6.0.1
```

Override it with `IDF_PATH_ROOT=/path/to/esp-idf-v6.0.1 ./scripts/build_firmware.sh`. If the export script is not available, the firmware build exits with a clear error.

## Local Configuration

Wi-Fi credentials must stay out of Git.

Create ignored `wifi.env` in the repository root:

```text
ssid: your-local-ssid
pw: your-local-password
```

Then build or flash normally:

```bash
./scripts/build_firmware.sh
```

`scripts/generate_wifi_config.sh` reads ignored `wifi.env` and writes ignored `main/config.local.h` for the ESP-IDF build. The firmware connects as a Wi-Fi station and logs the assigned IP address on serial.

For a stable address, prefer a DHCP reservation in the router for the ESP32-CAM MAC address. That keeps the firmware simple while still giving the device the same IP on every boot.

## Flash And Monitor

```bash
./scripts/flash_device.sh /dev/ttyUSB0
./scripts/monitor_serial.sh /dev/ttyUSB0
```

Boot mode on the ESP32-CAM-MB board:

1. Press and hold **BOOT**.
2. Press and release **RST**.
3. Release **BOOT**.
4. Run the flash command within roughly one second.

## Dataset Capture

After flashing, configure `main/config.local.h` with Wi-Fi credentials and read the device IP from serial logs. The prototype debug endpoint serves one JPEG per request:

```text
GET /debug/capture.jpg
```

Capture a local training batch from the workstation:

```bash
./scripts/collect_dataset.sh \
  --base-url http://DEVICE_IP \
  --count 100 \
  --lighting-label bright-room
```

Repeat with different `--lighting-label` values and optional camera controls such as `--brightness`, `--contrast`, `--saturation`, `--aec`, `--agc`, and `--awb`. Captures and manifests are written under ignored `tools/dataset/captures/` directories.

## Project Structure

```text
esp32-fever-dream/
├── CMakeLists.txt              # ESP-IDF project or host test project
├── VERSION                     # SemVer source of truth
├── LICENSE                     # GPLv3
├── dependencies.lock           # Pinned ESP-IDF managed component resolution
├── documents/
│   ├── 00_VISION.md
│   └── 01_PLAN.md
├── firmware/
│   ├── include/                # Host-testable firmware interfaces
│   └── src/                    # Host-testable firmware core
├── main/
│   ├── app_main.cpp            # ESP-IDF app entry
│   ├── CMakeLists.txt
│   ├── config.example.h        # Copy to ignored config.local.h
│   └── idf_component.yml       # Pinned ESP-IDF component deps
├── web/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/                      # Host unit tests
├── scripts/                    # Local pipeline, build, flash, dataset hooks
└── reports/                    # Review, model, and static analysis notes
```

## Implemented Core Modules

- `ReadingRecord`: compact success/failure record model with explicit status codes.
- `StorageRingBuffer`: host-tested bounded in-memory ring buffer prototype.
- `Recognition`: seven-segment digit primitive and display text validation.
- `ImagePreprocessor`: grayscale ROI validation, crop, and threshold helpers.
- `Diagnostics`: boot, failure, Wi-Fi, and time state snapshot.
- `TimeManager`: synchronized and estimated timestamp state.
- `ApiSerializer`: JSON serialization for status, current reading, historical readings, and errors.

## Versioning

`VERSION` is the single source of truth. Firmware and host builds read it at configure time and expose it through:

```cpp
fever::version::ProjectVersion()
```

The project starts at `0.0.0`. Per the project rule, later implementation commits should increment the patch version by one unless directed otherwise.

## Current Limitations

- Production HTTP handlers are not wired yet; serializers and web UI define the contract first.
- Ring-buffer persistence to flash is not implemented yet.
- Recognition has primitives and validation, but no real thermometer dataset yet.

## License

GPLv3. See `LICENSE`.
