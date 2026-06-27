# Timed Batch Labeling and Retraining Plan

Last updated: 2026-06-27.

## Situation

The current digit classifier is blocked by missing real examples for digits `5`,
`6`, `7`, and `8`. The last training audit (`reports/model_training_audit.md`)
showed:

| Check | Result |
| --- | --- |
| Minimum captures (300) | pass |
| Distinct readings (10) | **fail** — only 5 |
| All digits present | **fail** — 5, 6, 7, 8 missing |
| 20 samples per digit | **fail** |
| Held-out samples (50) | pass |

The current corpus covers only `29C 41%`, `29C 43%`, `30C 44%` and two
humidity-only fragments — all from 2026-06-25 captures.

## New Captures Available

Three directories of unlabeled images were collected today and yesterday that
are likely to close the digit gap:

| Capture directory | Images | Method | Time span | Status |
| --- | ---: | --- | --- | --- |
| `serial_timed_fast_20260627T1205Z` | **520** | USB serial, periodic cache | 09:59–11:46 UTC today (~1 h 47 min) | **unlabeled** |
| `http_300_aqs_20260626T2040Z` | 300 | HTTP, rapid burst | ~1 min yesterday evening | unlabeled |
| `serial20260626` | 93 | USB serial | 2026-06-26 positioning session | unlabeled |

The 520-image timed run is the primary target. It spans 1 h 47 min of
continuous 10-second captures, during which the AQS display changed temperature
and CO2 readings repeatedly. This is the main source for previously unseen
digits.

The 300-image HTTP burst was captured in under one minute at a fixed display
state. It cannot add digit diversity on its own, but is useful as additional
volume for whatever value was on screen.

## Why the Timed Run Covers the Missing Digits

Temperature in the lab during the capture window (10:00–11:46 UTC) is expected
to have ranged from roughly 26–29°C. CO2 readings typically vary between
400–900 ppm across a two-hour indoor window. Those ranges directly produce
digits `5`, `6`, `7`, `8` in temperature tens and hundreds, CO2 hundreds,
HCHO, and TVOC columns.

The display updates every 10 seconds; the firmware was running at 10-second
OCR intervals. Consecutive frames with the same display value will share a very
similar perceptual hash. Once hashes are computed, contiguous groups of near-
identical frames identify stable display states — each stable group shares one
label and can be labeled as a range.

## Labeling Strategy

### Step 1 — Run corpus audit

Audit all 520 images to detect quality and perceptual-hash clusters:

```sh
python3 tools/dataset/audit_capture_corpus.py \
    tools/dataset/captures/serial_timed_fast_20260627T1205Z \
    --output-dir build/audit_timed_fast_20260627
```

This produces `accepted.csv` with brightness, contrast, sharpness, and dhash
for each frame. Frames with `nearest_hash_distance` of 0 or 1 against the
previous accepted frame are duplicate display states; those with distance ≥ 4
mark a display change point.

### Step 2 — Generate a sparse contact sheet

Look at every 10th accepted frame in sequence to read display values
visually. This gives roughly 52 reference points across the 1 h 47 min run.
If the display changed every 10–60 seconds, this sample will hit most distinct
values.

A contact sheet showing the bottom strip ROI of each sampled frame makes the
change points easy to identify by eye.

### Step 3 — Label by range

Use `relabel_fixed_display_ranges.py` to apply temperature/humidity labels to
contiguous index ranges between identified change points.

Example workflow after identifying breakpoints manually:

```sh
# First: produce unlabeled base labels from the batch
python3 tools/dataset/label_fixed_display_batch.py \
    --dataset-dir tools/dataset/captures/serial_timed_fast_20260627T1205Z \
    --temperature-c 0 \
    --humidity-percent 0 \
    --output tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment.csv

# Then: overwrite ranges with real values observed from images
python3 tools/dataset/relabel_fixed_display_ranges.py \
    --input  tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment.csv \
    --output tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment.csv \
    --range 11-90:27:44 \
    --range 91-180:27:45 \
    --range 181-260:28:44 \
    # ...etc — fill in from the contact-sheet survey
```

All five AQS values must be labeled per frame: `co2_ppm`, `hcho_raw`, `tvoc_raw`,
`temperature_c`, and `humidity_percent`. If a field is not visible or uncertain
for a given range, mark those frames `valid=false` rather than guessing.

For the five-value label schema, the 2026-06-26 upright batch
(`live_upright_20260626T2309Z/labels_environment.csv`) is the reference format.

### Step 4 — Label the 300-image HTTP batch (optional)

If one stable display value is identifiable across `http_300_aqs_20260626T2040Z`,
label the whole batch at once:

```sh
python3 tools/dataset/label_fixed_display_batch.py \
    --dataset-dir tools/dataset/captures/http_300_aqs_20260626T2040Z \
    --temperature-c <VALUE> \
    --humidity-percent <VALUE> \
    --output tools/dataset/captures/http_300_aqs_20260626T2040Z/labels_environment.csv
```

If the display changed during the burst, mark the ambiguous frames invalid.

## Merge and Digit Audit

After labeling, merge all valid label CSVs into a single training corpus:

```sh
python3 tools/dataset/merge_label_csv.py \
    --labels tools/dataset/captures/approved_29c_43h_20260625T185939Z/labels_environment.csv \
    --labels tools/dataset/captures/training_baseline_manual_20260625T183552Z/labels_environment.csv \
    --labels tools/dataset/captures/daylight_changed_29c_43h_20260625T191248Z/labels_environment.csv \
    --labels tools/dataset/captures/live_mounted_29c_41h_20260625T195058Z/labels_environment.csv \
    --labels tools/dataset/captures/live_upright_20260626T2309Z/labels_environment.csv \
    --labels tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment.csv \
    --output models/generated/digit_dataset/merged_labels.csv
```

Then run the audit:

```sh
python3 scripts/audit_dataset.py \
    --labels models/generated/digit_dataset/merged_labels.csv \
    --output-md reports/model_training_audit.md
```

Training is blocked until the audit passes all checks. The blockers to clear:

| Check | Current | Target |
| --- | --- | --- |
| Distinct readings | 5 | ≥ 10 |
| All digits present | no (5,6,7,8 missing) | yes |
| Samples per digit | 0 for 5,6,7,8 | ≥ 20 each |

## Train/Validation/Test Split Strategy

Split by capture batch, not by individual frame. Frames from the same
10-second measurement window are nearly identical; mixing them across splits
leaks the display value and inflates accuracy.

Recommended split:

| Batch | Role |
| --- | --- |
| `approved_29c_43h_20260625T185939Z` | train |
| `training_baseline_manual_20260625T183552Z` | train |
| `daylight_changed_29c_43h_20260625T191248Z` | train |
| `live_mounted_29c_41h_20260625T195058Z` | train |
| First 80% of `serial_timed_fast_20260627T1205Z` frames | train |
| Last 20% of `serial_timed_fast_20260627T1205Z` frames | validation |
| `live_upright_20260626T2309Z` (3 frames) | validation |
| `http_300_aqs_20260626T2040Z` (if labeled, one stable value) | test |

The test set should contain **no frames from the same capture session as
training data** to give an honest estimate of real-world accuracy.

Minimum required before running training:

- At least 20 real samples for each digit `0`–`9`.
- At least 50 held-out validation/test frames.
- Synthetic augmentation is allowed for training only, never for validation or
  test.

## Retrain

Once the audit passes:

```sh
./scripts/train_model.sh
```

This calls `build_digit_dataset.py` to crop digit regions, then
`train_digit_classifier.py` to train the int8 model. Outputs:

```text
models/generated/digit_classifier_int8.tflite
firmware/generated/digit_classifier_model.h
reports/model_eval.md
reports/confusion_matrix.csv
```

## Acceptance Before Flashing

Do not flash until:

- Per-digit accuracy ≥ 99% on the held-out test set.
- Full five-value exact match accuracy ≥ 98% on held-out real frames.
- Host-side evaluator passes on `live_upright_20260626T2309Z` (currently 0/3
  exact five-value matches).
- Temporary firmware corrections for `29C/41%` and `27C/41%` are removed.
- Confidence threshold is raised back from the current 60% relaxed value.

## Known Risks

- The timed run's display values must be read manually from images; no
  auto-labeling is available for a fully unlabeled serial batch.
- CO2/HCHO/TVOC digit boxes in the firmware are still provisional; even a good
  model may fail if the crop coordinates are off. Consider firmware-side crop
  telemetry (a debug endpoint returning the 24×32 tensors) before final
  acceptance.
- The 300-image HTTP burst was taken in rapid succession; if the display did
  not change during that minute, the batch adds only volume for one reading,
  not digit diversity.
