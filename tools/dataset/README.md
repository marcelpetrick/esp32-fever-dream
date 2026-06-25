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

The recognition evaluator expects a CSV header with at least:

```csv
display_text
21.7
```

Add `predicted_display_text` when a recognizer can emit decoded values for the
same samples.
