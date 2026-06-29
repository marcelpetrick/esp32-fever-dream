# Fixed Display Batch Report

Generated UTC: `2026-06-25T18:35:11+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/camera_sweep_20260625T183448Z/bright_contrast`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/camera_sweep_20260625T183448Z/bright_contrast/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 8
- Splits: {'train': 7, 'validation': 1}
- Temperature label: `30C`
- Temperature Celsius: `30.0`
- Humidity percent: `44`
- Minimum ROI confidence: `0.0410`
- Median ROI confidence: `0.0483`
- P10 ROI confidence: `0.0464`
- Median ROI contrast: `2.15`
- Median ROI sharpness: `0.11`
- Low-quality samples: `8`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
