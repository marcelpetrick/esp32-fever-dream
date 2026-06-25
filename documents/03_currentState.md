# Current State

## Summary

The ESP32-CAM is connected to the local Wi-Fi network and can be reached by
hostname:

```text
esp32-fever-dream
```

The browser-testable local dashboard is available while the local web server is
running:

```text
http://127.0.0.1:8080/?device=esp32-fever-dream
```

The dashboard can display the live ESP32-CAM debug stream from the device. This
proves the current camera, Wi-Fi, browser, and debug HTTP path.

## Firmware State

- Latest flashed commit during this loop: `51c2baa`
- Firmware version source of truth before this document commit: `0.0.13`
- Device hostname: `esp32-fever-dream`
- Health endpoint:

```text
http://esp32-fever-dream/debug/health
```

- Live capture endpoint:

```text
http://esp32-fever-dream/debug/capture.jpg
```

The debug capture endpoint now streams JPEGs directly from the camera frame
buffer instead of copying the frame into another owned buffer first. This made
repeated capture more stable for dataset acquisition.

CORS headers are enabled on the debug endpoints so the local dashboard served
from `127.0.0.1` can access the ESP32 debug server.

## Local Dataset State

Captured data is stored locally under the ignored dataset tree:

```text
tools/dataset/captures/
```

The main usable captured batch is:

```text
tools/dataset/captures/training_baseline_manual_20260625T183552Z
```

Important local files in that batch:

```text
labels_environment.csv
fixed_display_report.md
recognition_eval.md
bottom_strip_contact_labeled.jpg
```

The confirmed labels for that batch are:

- Temperature: `29C`
- Humidity: `43%`

Best measured first-pass camera settings for this mounted setup:

```text
framesize=vga
quality=12
brightness=2
contrast=2
awb=0
aec=0
agc=0
```

The tuned batch result:

- 100 successful captures
- 1 recovered HTTP retry
- Median ROI confidence: `0.5219`
- P10 ROI confidence: `0.5127`
- Low-quality samples: `1 / 100`

This is good enough for acquisition, ROI, and browser-stream validation. It is
not enough for training a real TinyML OCR model.

## TinyML State

No TinyML TFLite model was trained from the current dataset.

Reason: all usable labels currently represent the same reading, `29C 43%`. A
model trained on this batch would learn a constant answer instead of learning
digit recognition.

The dataset audit currently blocks training with these findings:

- Valid rows: `100`
- Required valid captures: `300`
- Distinct readings: `1`
- Required distinct readings: `10`
- Held-out validation/test rows: `20`
- Required held-out rows: `50`
- Digit classes present: `2`, `3`, `4`, `9`
- Missing digit classes: `0`, `1`, `5`, `6`, `7`, `8`

The audit report is tracked at:

```text
reports/model_training_audit.md
```

The training entrypoint is:

```sh
./scripts/train_model.sh --labels tools/dataset/captures/training_baseline_manual_20260625T183552Z/labels_environment.csv
```

It intentionally refuses to train until the dataset is varied enough.

## Next Steps

Do not take many duplicate pictures of the same value. Instead, collect a small
number of samples whenever the displayed temperature or humidity changes.

Training becomes meaningful when the dataset has:

- At least 300 successful real captures.
- At least 10 distinct full readings.
- Digits `0` through `9` represented.
- At least 20 samples per digit class after cropping.
- At least 50 validation/test frames.
- Some intentionally worse lighting or bad examples.

Once the audit passes, implement the digit-crop trainer and then export an int8
TFLite model for ESP32-side inference.
