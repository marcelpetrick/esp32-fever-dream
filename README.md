# ESP32 Fever Dream

Local ESP32-CAM thermometer readout firmware. The target device captures a fixed-position digital thermometer once per minute, recognizes the displayed temperature, stores readings in bounded local storage, and serves a dashboard plus raw API endpoints directly from the ESP32.

**Status: implementation bootstrap.** Host-side core modules, tests, static web UI, firmware skeleton, pipeline scripts, GPLv3 license, and SemVer source of truth are present. Hardware capture, persistent flash storage, live HTTP handlers, and the full one-minute device loop are still in progress.

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
- Python 3 for future dataset/model tooling.

## Local Pipeline

```bash
./scripts/check_all.sh
```

Stages:

1. clang-format check.
2. Host CMake configure.
3. Host C++ build.
4. Host unit tests.
5. cppcheck and clang-tidy when available.
6. Static web asset check.
7. Doxygen generation.

The host pipeline is intended to run without attached hardware.

## Build Firmware

ESP-IDF is not vendored. Source the pinned local ESP-IDF environment first:

```bash
source ~/.local/opt/esp-idf-v6.0.1/export.sh
./scripts/build_firmware.sh
```

If `idf.py` is not available, the firmware build script exits with a clear error.

## Local Configuration

Wi-Fi credentials must stay out of Git.

```bash
cp main/config.example.h main/config.local.h
```

Edit `main/config.local.h` for the local network. The `.gitignore` excludes `config.local.h`.

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

## Project Structure

```text
esp32-fever-dream/
├── CMakeLists.txt              # ESP-IDF project or host test project
├── VERSION                     # SemVer source of truth
├── LICENSE                     # GPLv3
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

- ESP-IDF is not installed or sourced in the current shell, so only host-side checks can run here.
- Camera capture is not wired yet.
- HTTP handlers are not wired yet; serializers and web UI define the contract first.
- Ring-buffer persistence to flash is not implemented yet.
- Recognition has primitives and validation, but no real thermometer dataset yet.

## License

GPLv3. See `LICENSE`.
