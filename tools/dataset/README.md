# Dataset Inputs

Place local display-text label CSV files here when they are safe to keep in the
working tree.

Raw captures live under ignored directories such as `tools/dataset/captures/`.
Use the ESP32 debug capture endpoint with:

```sh
./scripts/collect_dataset.sh \
  --base-url http://DEVICE_IP \
  --count 100 \
  --lighting-label bright-room
```

Repeat the command for different lighting labels. The script writes JPEG files
and a `manifest.csv`; fill the `display_text` column after capture to create
labels for OCR evaluation and TinyML training.

If the ESP32-CAM is only reachable over USB serial, use:

```sh
./scripts/collect_serial_dataset.sh \
  --port /dev/ttyUSB0 \
  --count 30 \
  --lighting-label usb-fallback \
  --framesize vga \
  --quality 12
```

The serial protocol sends `CAPTURE_JPEG` to the device and decodes the returned
base64 JPEG into the same ignored capture directory structure.

For the first fixed-layout acquisition loop, create a local label and ROI-quality
report after visually confirming the temperature and humidity in the captures:

```sh
python3 tools/dataset/label_fixed_display_batch.py \
  --dataset-dir tools/dataset/captures/baseline_YYYYMMDDTHHMMSSZ \
  --temperature-c 29 \
  --humidity-percent 43
```

This writes ignored local artifacts into the capture directory:

- `labels_environment.csv`
- `fixed_display_report.json`
- `fixed_display_report.md`
- `bottom_strip_contact_labeled.jpg`

The baseline labeler intentionally records human-confirmed fixed-layout labels.
It is not a trained OCR model and should not be used as final accuracy evidence
unless the displayed values vary across a held-out validation set.

## Ollama label proposals

Vision-model OCR is an untrusted first pass. It writes
`labels_ollama_proposals.csv`, never training ground truth:

```sh
python3 tools/dataset/ollama_label_batch.py \
  --dataset-dir tools/dataset/captures/<batch> \
  --model qwen3-vl:4b
```

Requests use structured output, a bounded token count, and a hard total
deadline. Successful proposals are retained on resume while rejected and error
rows are retried. Do not pass this proposal CSV to the training pipeline;
promote only human-reviewed values to `labels_environment.csv`.

Prepare a review queue, edit its decision/correction columns, and promote the
approved rows:

```sh
python3 tools/dataset/review_ollama_labels.py prepare \
  --proposals tools/dataset/captures/<batch>/labels_ollama_proposals.csv \
  --audit-csv tools/dataset/captures/<audit>/capture_corpus_audit.csv \
  --output tools/dataset/captures/<batch>/labels_ollama_review_queue.csv

python3 tools/dataset/review_ollama_labels.py promote \
  --queue tools/dataset/captures/<batch>/labels_ollama_review_queue.csv \
  --output tools/dataset/captures/<batch>/labels_environment.csv
```

`review_decision` must be `approve`, `correct`, or `reject`. Approved/corrected
rows require `reviewer` and an ISO-8601 `reviewed_at_utc`. Training refuses
unreviewed Ollama rows.

The best first-pass camera settings measured on the mounted setup were:

```sh
./scripts/collect_dataset.sh \
  --base-url http://esp32-fever-dream \
  --count 100 \
  --interval 1 \
  --lighting-label baseline_manual_bright \
  --framesize vga \
  --quality 12 \
  --brightness 2 \
  --contrast 2 \
  --awb 0 \
  --aec 0 \
  --agc 0
```

The recognition evaluator expects a CSV header with at least:

```csv
display_text
21.7
```

Add `predicted_display_text` when a recognizer can emit decoded values for the
same samples.

## Capture corpus audit

Audit captures before labeling or training so malformed, badly exposed, blurry,
unlocatable, and near-duplicate frames do not inflate the dataset:

```sh
python3 tools/dataset/audit_capture_corpus.py \
  tools/dataset/captures/serial20260626 \
  tools/dataset/captures/another_session \
  --output-dir tools/dataset/captures/audit_20260627 \
  --strict \
  --min-accepted 500
```

The command recursively scans `.jpg` and `.jpeg` files. It verifies JPEG decode
and the expected 640x480 dimensions, invokes the same orientation-aware display
locator used by `tools/model_training/build_digit_dataset.py`, and measures the
located display's mean brightness, contrast standard deviation, and Laplacian
sharpness variance. A 64-bit perceptual difference hash rejects frames that are
effectively duplicates of an earlier accepted frame.

Outputs are `capture_corpus_audit.csv`, with one decision and rejection reason
per image, and `capture_corpus_audit.json`, with thresholds, counts, rejection
totals, and metric distributions. `--strict` returns exit code 2 when fewer than
`--min-accepted` frames pass all gates. Default gates can be adjusted with
`--min-brightness`, `--max-brightness`, `--min-contrast`, `--min-sharpness`, and
`--duplicate-distance`; set duplicate distance to `-1` only when intentionally
retaining repeated frames for diagnostics.
## Cycle-Aware AQS Capture

For long-running five-value collection, capture once after each completed
firmware measurement cycle. This avoids competing with the camera while OCR is
active and records the simultaneous device result as untrusted prediction
provenance:

```sh
./scripts/collect_timed_aqs.sh \
  --base-url http://esp32-fever-dream \
  --output tools/dataset/captures/timed_upright_<timestamp> \
  --count 520 \
  --lighting-label timed_daylight_upright
```

The command validates JPEG decoding and dimensions before appending a row to
`manifest.csv`. Fields prefixed with `device_` are model predictions and must
not be treated as training labels until independently reviewed.
