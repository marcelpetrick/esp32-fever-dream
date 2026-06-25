# On-Device OCR And TinyML Plan

## 1. Goal

Recognize the temperature shown on a fixed-position digital thermometer from one ESP32-CAM capture, fully on-device, inside the one-minute measurement cadence.

The target cycle is:

1. Capture one image.
2. Extract the thermometer display region.
3. Normalize and segment the display.
4. Decode the temperature value.
5. Validate plausibility and confidence.
6. Store a success or explicit failure record.

The target is not general OCR. The target is robust extraction of one known display from one known physical setup.

## 2. Timing Answer

Yes, one capture plus recognition should fit comfortably inside one minute on the known ESP32-CAM class hardware if the recognition pipeline avoids whole-frame neural OCR.

Expected time budget after implementation tuning:

| Step | Expected range | Notes |
| --- | ---: | --- |
| Camera wake/init when already powered | 100 ms to 2 s | Depends on camera state and whether deep sleep is used. |
| VGA JPEG capture | 100 ms to 2 s | Must be measured on the actual module. |
| ROI extraction and grayscale/threshold preprocessing | 10 ms to 500 ms | Depends on whether JPEG decode is whole-frame or ROI-limited. |
| Classical seven-segment decode | under 50 ms | Small binary ROI operations. |
| TinyML digit fallback, if used | 50 ms to 2 s | Small per-digit int8 classifier only. |
| Validation, storage, API state update | under 100 ms | Already small relative to capture. |

The one-minute requirement becomes risky only if we try to run a large whole-frame detector/OCR model, repeatedly recapture, or keep large tensors in PSRAM. A reported ESP32-S3 large-model case took about 60 seconds for one roughly 2 MB model with a 5 MB tensor arena in PSRAM, which is the pattern this project should avoid.

## 3. Hardware And Image Constraints

Known target:

- AI-Thinker ESP32-CAM.
- OV2640 camera.
- ESP32-D0WDQ6 class chip.
- 4 MB flash.
- PSRAM expected and required for this project.
- Fixed camera-to-thermometer geometry.
- One reading per minute.

The user expects 640x480 captures with RGB most likely. Memory cost:

| Format | 640x480 memory |
| --- | ---: |
| RGB888 | 921,600 bytes |
| RGB565 | 614,400 bytes |
| Grayscale | 307,200 bytes |
| JPEG | Variable, usually much smaller, decode needed |

Espressif's `esp32-camera` guidance is important here:

- OV2640 supports JPEG and RGB/YUV formats.
- For original ESP32, Espressif warns not to use sizes above QVGA when not JPEG.
- RGB/YUV writes put high strain on PSRAM and can lose data, especially with Wi-Fi enabled.
- If RGB data is needed, Espressif recommends capturing JPEG and converting to RGB.

Project decision:

- Capture `FRAMESIZE_VGA` as JPEG for the main path.
- Decode only what is needed for the display ROI when practical.
- Convert to grayscale as early as possible.
- Keep the neural model input at digit-crop scale, never 640x480.

Sources:

- Espressif `esp32-camera`: https://github.com/espressif/esp32-camera
- Espressif `esp-tflite-micro`: https://github.com/espressif/esp-tflite-micro
- Espressif Component Registry `esp-tflite-micro`: https://components.espressif.com/components/espressif/esp-tflite-micro
- Google LiteRT for Microcontrollers: https://developers.google.com/edge/litert/microcontrollers/overview
- Google integer quantization: https://developers.google.com/edge/litert/conversion/tensorflow/quantization/post_training_integer_quant

## 4. Recommended Architecture

Use a hybrid recognition stack:

1. Classical computer vision owns localization, cleanup, segmentation, decimal point detection, and plausibility checks.
2. Seven-segment rule decoding is the first recognizer.
3. A small int8 TFLite Micro digit classifier is added only if real captures show the rule decoder is not reliable enough.
4. Full-reading validation rejects ambiguous values instead of guessing.

This is the best fit because the display is fixed, the value format is constrained, and the hardware is small. A generic OCR network is unnecessary and would consume memory, flash, power, and schedule margin without improving the controlled-case problem enough to justify it.

## 5. Candidate Approaches

### 5.1 Classical Seven-Segment OCR

Pipeline:

- Capture JPEG at VGA.
- Convert to grayscale ROI.
- Optional lens/perspective correction using fixed calibration points.
- Normalize contrast.
- Threshold adaptively.
- Locate digit bounding boxes.
- Detect decimal point and optional minus sign.
- Sample seven segment zones per digit.
- Decode each digit with known segment masks.
- Validate final text through `ParseDisplayText`.

Advantages:

- Fastest path.
- Smallest RAM and flash footprint.
- Explainable failure modes.
- Easy to host-test from captured images.
- No model training dependency.

Risks:

- Sensitive to glare, shadows, low LCD contrast, reflections, and display ghosting.
- Needs careful calibration for the real camera mount.
- Segment thresholds may drift across lighting conditions.

Decision:

- Implement this first.
- Treat it as production path if it reaches the accuracy threshold on real captures.

### 5.2 Whole-Frame Neural OCR

Examples:

- Generic OCR detector plus recognizer.
- CNN over 640x480 frame.
- Object detection model over whole image.

Advantages:

- Could tolerate layout variation.

Risks:

- Wrong scale for ESP32-CAM.
- Large frame tensors exceed SRAM and push work into PSRAM.
- Harder to debug and validate.
- Likely unnecessary for a fixed display.
- More likely to threaten the one-minute cadence.

Decision:

- Do not use whole-frame neural OCR.
- Reconsider only if the hardware changes to a larger ESP32-S3/P4 class board and the physical setup cannot be stabilized.

### 5.3 TinyML Per-Digit Classifier

Pipeline:

- Use classical preprocessing to segment each digit.
- Resize each digit crop to a small grayscale tensor such as 16x24, 20x28, or 24x32.
- Classify classes `0` through `9`, plus optional blank/minus if needed.
- Use decimal point from classical detection.
- Combine digit probabilities into one full-reading confidence.
- Validate against physical range and expected display format.

Candidate model:

- Input: one grayscale digit crop.
- Quantization: full int8.
- Layers: tiny CNN or depthwise-separable CNN.
- Operators: keep to `CONV_2D`, `DEPTHWISE_CONV_2D` if needed, `MAX_POOL_2D`, `RESHAPE`, `FULLY_CONNECTED`, `SOFTMAX`.
- Model size target: under 50 KB preferred, under 150 KB maximum.
- Tensor arena target: under 150 KB preferred, under 300 KB maximum.

Advantages:

- More tolerant than segment masks.
- Still small enough for ESP32 if constrained.
- Can be benchmarked per digit and per full reading.

Risks:

- Requires labeled real data.
- Quantization can change behavior; host and device outputs must be compared.
- TFLite Micro operator set must be pinned and minimal.
- PSRAM tensor arenas can be slower than internal SRAM.

Decision:

- Use this as fallback or verifier if classical OCR misses the target.
- Do not make it the first implementation dependency.

### 5.4 External Training, On-Device Inference

Training should happen locally on the development machine, not on the ESP32.

Tooling:

- Python image preprocessing and labeling helpers.
- TensorFlow/Keras training if TinyML is needed.
- TFLite conversion with full integer quantization.
- C array or binary model artifact generation.
- Host-side test runner that compares expected labels, TFLite output, and firmware-compatible postprocessing.

Device inference options:

- Preferred: `espressif/esp-tflite-micro` component, pinned in `main/idf_component.yml` if selected.
- Alternative: vendor-neutral upstream TFLite Micro source integration only if the Espressif component blocks IDF 6.0.1.
- Avoid Edge Impulse SDK unless its workflow clearly saves time and the generated firmware artifact remains reproducible and reviewable. Its component footprint is larger than a minimal hand-integrated classifier.

## 6. Accuracy Targets

Measure both per-digit and full-reading accuracy. Full-reading accuracy matters most because one wrong digit creates a wrong temperature.

Acceptance thresholds:

- Full-reading exact accuracy: at least 99.0% on the controlled validation set.
- Per-digit accuracy: at least 99.5% if using digit classification.
- False accept rate: under 0.1% for invalid/ambiguous images.
- Ambiguous images should become failure records, not guessed readings.
- Confidence calibration: samples below threshold should correlate with actual error risk.

Operational threshold:

- Prefer a missed reading over a wrong reading.
- A single failed minute is acceptable.
- Silent wrong values are not acceptable.

## 7. Dataset And Benchmark Plan

We need real benchmark images before choosing final precision claims.

Minimum dataset:

- 300 labeled captures from the real mounted camera.
- Include the normal expected value range.
- Include at least 30 captures near each visually tricky digit pair: `1/7`, `3/8`, `5/6`, `8/9`, `0/8`.
- Include decimal-point visibility variations.
- Include lighting variation: daylight, room light, dim, glare if likely.
- Include at least 50 negative or bad captures: blur, blocked display, partial display, overexposure, underexposure.

Preferred dataset:

- 1,000 to 2,000 labeled full-frame captures.
- At least 100 captures held out and never used for tuning.
- Repeated same temperature values across different lighting and camera exposure settings.

Label format:

```csv
image_id,temperature_text,temperature_centi_c,valid,notes
capture_000001.jpg,21.7,2170,true,normal
capture_000002.jpg,,0,false,blurred
```

Benchmark script outputs:

- Full-reading accuracy.
- Per-character confusion matrix.
- False accepts.
- False rejects.
- Median and p95 preprocessing time on host.
- Device timing once firmware benchmark exists.
- Memory use for model arena if TinyML is enabled.

Action needed:

- Schedule a real-image benchmark as soon as the camera can capture from the mounted setup.
- Do not commit to final OCR strategy until this benchmark exists.

## 8. Device Benchmark Plan

Add a firmware benchmark mode that can run without changing normal behavior:

- Capture one frame.
- Measure capture time with `esp_timer_get_time`.
- Measure JPEG decode or ROI extraction time.
- Measure threshold/segmentation time.
- Measure rule decoder time.
- If enabled, measure TinyML per-digit and total inference time.
- Log free heap, minimum free heap, PSRAM use, and largest free block.
- Return benchmark data over serial and `/api/v1/debug/recognition` when debug endpoints are enabled.

Acceptance:

- p95 total capture-to-result under 10 seconds.
- Absolute maximum under 30 seconds.
- One-minute cadence remains safe with retries disabled.
- No watchdog reset.
- No heap fragmentation trend across 24 hours.

## 9. Firmware Integration Plan

### Phase A: Capture And Calibration

- Keep VGA JPEG capture.
- Add debug capture export path.
- Store camera settings in config.
- Add fixed ROI config in pixels.
- Add optional ROI overlay metadata for the web/debug view.

Acceptance:

- Real captures are downloadable.
- ROI contains the display in at least 95% of normal captures.
- Camera settings are repeatable after reboot.

### Phase B: Classical OCR

- Add host-side image loader in `tools/recognition_eval`.
- Implement grayscale ROI conversion.
- Implement adaptive threshold options.
- Implement digit segmentation and decimal point detection.
- Extend firmware `Recognition` with structured segment evidence.
- Reuse `ParseDisplayText` for final validation.

Acceptance:

- Classical OCR benchmark report exists in `reports/model_eval.md`.
- Host tests cover segment masks, decimal placement, parsing, and invalid values.
- Firmware build remains warning-free.

### Phase C: Device Timing

- Add firmware timing counters for capture, preprocessing, recognition, and storage.
- Expose latest timing in diagnostics.
- Run at least 100 device cycles.

Acceptance:

- p95 capture-to-result is measured.
- Memory headroom is documented.
- Watchdog settings remain justified.

### Phase D: TinyML Decision Gate

Proceed to TinyML only if one is true:

- Classical full-reading accuracy is below 99.0%.
- False accepts are above 0.1%.
- Lighting/display variability cannot be fixed mechanically.
- Segment evidence is frequently ambiguous but digit crops remain visually readable.

Do not proceed to TinyML if:

- Classical OCR passes thresholds.
- Failures are mainly capture quality or physical mounting issues.
- More lighting control would solve the issue more cheaply.

### Phase E: TinyML Classifier

- Add `tools/model_training`.
- Generate digit crops from labeled full-frame captures.
- Train tiny int8 classifier.
- Convert and pin model artifact.
- Add host test comparing known TFLite outputs.
- Add optional firmware recognizer behind the existing recognition interface.

Acceptance:

- Model is reproducible from scripts.
- `scripts/check_all.sh` can validate the checked-in model metadata.
- Firmware inference p95 stays below 2 seconds total for all digits.
- Combined full-reading accuracy improves over classical OCR.

## 10. Data Extraction Rules

The final reading should be accepted only when all constraints pass:

- Display text grammar is valid: optional minus sign, digits, optional one decimal point.
- Value is within configured physical temperature range.
- Decimal point position matches the thermometer format.
- Per-digit or segment confidence is above threshold.
- Full-reading confidence is above threshold.
- Temporal sanity check passes unless this is the first reading.

Temporal sanity checks:

- Reject or flag jumps larger than a configured delta per minute.
- Keep status metadata so a real sudden change can be diagnosed rather than hidden.
- Do not smooth the stored raw reading silently.

## 11. Precision Strategy

Best precision comes from controlling the input before adding ML:

- Fixed mount.
- Fill the frame with the display enough that the ROI is large.
- Avoid reflective angles.
- Disable or stabilize auto exposure/white balance after calibration if needed.
- Prefer diffuse lighting.
- Use a fixed ROI and known display grammar.
- Reject low-confidence readings.

Model sophistication is secondary. A small, well-lit, well-cropped seven-segment display should outperform a generic OCR approach on this hardware.

## 12. Open Questions

- Exact thermometer display type and digit geometry.
- Whether the display has a minus sign, degree symbol, `C`, battery icon, or unit text inside the ROI.
- Whether the thermometer updates continuously or only after a button/action.
- Whether Wi-Fi is active during capture or can be disabled briefly.
- Whether deep sleep is required in the first complete device loop.
- Whether the user wants failed images retained locally for later labeling.

## 13. Immediate Next Steps

1. Implement debug capture export from the ESP32-CAM.
2. Capture the initial benchmark dataset from the mounted setup.
3. Label at least 300 images.
4. Build the host classical OCR benchmark.
5. Decide whether TinyML is necessary from measured accuracy, not preference.
6. If needed, add pinned `espressif/esp-tflite-micro` and train a tiny per-digit int8 classifier.

