# TinyML TFLite Training Plan

## Decision

Do not train a TinyML model from the current captured batch.

The current usable dataset has 100 real images from the mounted ESP32-CAM setup,
but every label is the same reading:

- Temperature: `29C`
- Humidity: `43%`

Training a digit classifier on that data would produce a model that can memorize
one display state. It would not learn OCR, it would not generalize to new
temperatures or humidity values, and any TFLite artifact produced from it would
be misleading.

## What Is Missing

Minimum data required before training:

- At least 300 successful real captures.
- At least 10 distinct full readings.
- All digit classes `0` through `9` visible in either temperature or humidity.
- At least 20 samples per digit class after cropping.
- At least 50 held-out validation/test images.
- Multiple lighting labels, including the tuned baseline and at least one worse
  lighting condition.
- Negative examples: blurred, blocked, overexposed, underexposed, and partial
  display frames.

Current gap:

- Only one full reading.
- Missing several digit classes.
- No true validation of changing values.
- No negative examples.

## Model Shape

Use the hybrid approach from the vision document:

1. Fixed ROI crop locates the bottom temperature/humidity strip.
2. Classical preprocessing segments digit crops.
3. A tiny int8 digit classifier handles only per-digit classification.
4. Rule-based postprocessing assembles `temperature_c` and `humidity_percent`.
5. Plausibility and confidence gates reject ambiguous readings.

Target model:

- Input: one grayscale digit crop, likely `20x28` or `24x32`.
- Output classes: `0` through `9`, plus `blank` and `invalid` if needed.
- Quantization: full int8.
- Preferred model size: under 50 KB.
- Maximum model size: 150 KB.
- Tensor arena target: under 150 KB.

## Training Pipeline

The local training command is:

```sh
./scripts/train_model.sh \
  --labels tools/dataset/captures/training_baseline_manual_YYYYMMDDTHHMMSSZ/labels_environment.csv
```

The command first audits the dataset. Training is blocked until the audit passes.
This prevents accidentally producing a model that only learns a constant answer.

When the audit passes, the training implementation should:

1. Read full-frame labels.
2. Crop the fixed temperature and humidity ROIs.
3. Segment individual digit crops.
4. Split by capture into train, validation, and test.
5. Train a small Keras CNN locally.
6. Quantize to int8 TFLite using representative digit crops.
7. Export:
   - `models/generated/thermometer_digit_model_int8.tflite`
   - `firmware/generated/model_data.cc`
   - `firmware/generated/model_data.h`
   - `reports/model_eval.md`
   - `reports/confusion_matrix.csv`

## Current Browser-Testable Loop

Until production recognition endpoints are implemented, the local dashboard can
be opened against the live ESP32 debug stream:

```sh
python3 -m http.server 8080 --directory web
```

Then open:

```text
http://127.0.0.1:8080/?device=esp32-fever-dream
```

The page shows the real live JPEG stream from:

```text
/debug/capture.jpg
```

This verifies camera, Wi-Fi, and browser connectivity while the TinyML training
gate waits for a varied dataset.
