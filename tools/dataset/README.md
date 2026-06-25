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
