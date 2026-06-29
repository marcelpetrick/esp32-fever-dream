# Dataset and Camera Configuration Review — 2026-06-29

## 1. Training data inventory

### All capture directories

| Directory | Valid | Format | CO₂ range | Notes |
|---|---|---|---|---|
| `baseline_20260625T182331Z` | 100 | legacy temp+hum | — | excluded (see below) |
| `stability_20260625T183410Z` | 20 | legacy temp+hum | — | excluded (see below) |
| `training_baseline_manual_20260625T183552Z` | 100 | legacy temp+hum | — | 29C 43% only |
| `approved_29c_43h_20260625T185939Z` | 40 | legacy temp+hum | — | 29C 43% only |
| `daylight_changed_29c_43h_20260625T191248Z` | 30 | legacy temp+hum | — | 29C 43% only |
| `live_mounted_29c_41h_20260625T195058Z` | 20 | legacy temp+hum | — | 29C 41% only |
| `live_upright_20260626T2309Z` | 3 | 5-field | 442–446 ppm | |
| `serial_timed_fast_20260627T1205Z` | 34 | 5-field (reviewed) | 574–838 ppm | |
| **TOTAL** | **347** | | | |

### Why `baseline` and `stability` are excluded

Both were captured before CO₂/HCHO/TVOC fields were introduced.  They carry
only temperature + humidity in a `display_text` string (`"30C 44%"`), so
`build_digit_dataset.py` could only extract 4 digit crops per frame instead
of 16.  Including them would not help pass any failing audit check — digit 0
already has 182 occurrences — and would add 120 more `capture_batches_split_exclusive`
violations.  They are kept on disk as historical reference.

### Effective training corpus

Only the 6 five-field-capable directories enter the merge:

| Check | Value | Target | Gap |
|---|---|---|---|
| Trusted valid frames | **227** | 300 | **73** |
| Heldout (val+test) | 46 | 50 | 4 |
| Distinct readings | 22 | 10 | ✓ |
| Digit 0–9 all ≥ 20× | ✓ | — | — |
| Untrusted labels | 0 | 0 | ✓ |

Digit distribution (current):

```
0: 182   1:  46   2: 245   3: 216   4: 266
5:  48   6:  41   7:  57   8:  52   9: 199
```

Remaining audit blockers are all quantity-only:
`minimum_captures`, `heldout_samples`, `minimum_validation`, `minimum_test`,
and `capture_batches_split_exclusive` (split assignments are per-row, not
per-batch — needs one-time re-assignment).

### How to reach 300

Resume the timed batch (475 frames remaining):

```sh
python3 tools/dataset/ollama_label_batch.py \
  --dataset-dir tools/dataset/captures/serial_timed_fast_20260627T1205Z \
  --model qwen3-vl:4b --num-ctx 2048 --shuffle \
  --lighting-label timed_daylight_usb

python3 tools/dataset/review_ollama_labels.py promote \
  --queue tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_ollama_review_queue.csv \
  --output tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment.csv \
  --auto-approve
```

73 more valid frames at the current ~84% valid rate ≈ ~87 frames to process.
At 50–160 s/frame (warm inference) ≈ 1.2–3.9 hours.

---

## 2. OCR invariance

The OCR pipeline operates in two stages: **display locator** (at
dataset-build time) and **digit classifier** (at inference).

### What the locator does

`locate_display()` scans the full VGA frame for the display's colour bar
(the blue/green strip along the left edge of the AQS LCD).  If found, all
digit crop boxes are computed as **percentages of the located display
bounds** via `resolve_relative_box()`.  If not found, the pipeline falls
back to hard-coded absolute pixel coordinates.

### Rotation invariance

| Angle | Handled? |
|---|---|
| 0° (display upright) | ✓ — primary path |
| 180° (display upside-down) | ✓ — locator tries both and picks higher score |
| 90° / arbitrary tilt | ✗ — not supported; locator returns None → fallback boxes |

**Current training data**: mostly 0° captures; `live_upright_20260626T2309Z`
adds one 180° batch.  Confidence with arbitrary mounting angles is low.

### Distance / zoom invariance

When the locator **succeeds**: crop boxes are relative to display width, so
the same digit percentage is cropped regardless of how far the camera is
from the display.  The crop is then resampled to 24×32 px.
**Distance-invariant as long as the display fills at least ~140 px wide.**

When the locator **fails** (display too small, occluded, or tilted >≈15°):
absolute fallback pixel boxes are used → not distance-invariant.

### Practical limits

- Minimum display width in frame: ~140 px (hard check in locator).
- The locator will fail if display is rotated more than ≈15° out of upright/inverted.
- Lens distortion is not corrected, so corner digits on frames where the
  display occupies most of the frame may appear slightly keystone-distorted.

---

## 3. Camera configuration

### Current settings (`firmware/src/camera_manager.cpp`)

```
framesize    : VGA (640×480)
jpeg_quality : 8   (0 = lossless, 63 = worst; 8 is near-lossless)
grab_mode    : CAMERA_GRAB_WHEN_EMPTY (single buffered)

sensor:
  vflip / hmirror : 1 / 1   (AI-Thinker orientation correction)
  brightness      : +2       (manual digital boost)
  contrast        : +2       (manual digital boost)
  saturation      :  0
  whitebal        : 1        (AWB on)
  exposure_ctrl   : 1        (AEC on)
  gain_ctrl       : 1        (AGC on)
```

### What is not configured

| Setting | Default | Recommended | Reason |
|---|---|---|---|
| `set_bpc` | off | **on** | removes hot/stuck pixels from OV2640 sensor |
| `set_wpc` | off | **on** | removes overexposed pixel clusters |
| `set_lenc` | off | **on** | OV2640 lens correction; reduces vignetting at frame edges |
| `set_raw_gma` | off | **on** | raw gamma; improves mid-tone clarity on LCD text |
| `set_gainceiling` | 2 dB | consider 4–6 dB | allows more aggressive AGC in marginal light |
| `set_aec2` | off | leave off | AEC2 is for night-mode; our LCD is bright |

### Concern: manual brightness + contrast boost

`brightness=2` and `contrast=2` apply a **digital boost on top of AEC/AGC**.
On a bright backlit LCD, AEC should converge on good exposure without a
manual lift.  The manual boost risks clipping digit segments to white (losing
stroke detail) and creating locally overexposed halos around bright elements.

**Recommendation**: set `brightness=0, contrast=0` and let AEC/AGC alone
control exposure.  Verify by capturing a test frame and checking that no
digit segments clip to pure white.

### Recommendation summary

Add to `camera_manager.cpp` sensor init block:

```cpp
sensor->set_bpc(sensor, 1);
sensor->set_wpc(sensor, 1);
sensor->set_lenc(sensor, 1);
sensor->set_raw_gma(sensor, 1);
sensor->set_brightness(sensor, 0);   // was 2 — let AEC control
sensor->set_contrast(sensor, 0);     // was 2 — let AEC control
```

**Important**: new training data should be captured AFTER changing camera
settings, not before.  The digit classifier learns the visual style of the
training images; inference images must match.  If settings change mid-dataset,
re-capture at least one full lighting-condition batch to anchor the new style.

### JPEG quality note

`jpeg_quality=8` (near-lossless) is correct for a training dataset.  JPEG
artefacts around sharp digit edges would degrade both the locator and the
digit crops.  Keep this setting.

---

## 4. Next steps

1. **Apply camera fix** — update `brightness=0, contrast=0`, add
   BPC/WPC/lenc/raw_gma.
2. **Capture one fresh batch** under the new settings to anchor the style.
3. **Resume timed labeling** — 73 more valid frames needed (~87 frames to
   process, ~1–4 hours GPU time).
4. **Fix split assignments** — reassign splits batch-by-batch so every
   capture directory is in exactly one split:
   - `baseline_*`, `approved_*`, `daylight_*`, `live_mounted_*` → train
   - `live_upright_*` → validation
   - `serial_timed_fast_*` → test (or train once enough heldout exists)
5. **Build digit dataset and train** once audit passes all checks.
6. **Remove firmware workarounds** — temporary 29C/41% and 27C/41% corrections
   in `tinyml_display_recognizer.cpp`, restore confidence threshold to 85%+.
