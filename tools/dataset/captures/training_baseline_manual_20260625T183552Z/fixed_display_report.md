# Fixed Display Batch Report

Generated UTC: `2026-06-25T18:38:28+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/training_baseline_manual_20260625T183552Z`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/training_baseline_manual_20260625T183552Z/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 100
- Splits: {'test': 10, 'train': 80, 'validation': 10}
- Temperature label: `29C`
- Temperature Celsius: `29.0`
- Humidity percent: `43`
- Minimum ROI confidence: `0.1462`
- Median ROI confidence: `0.5219`
- P10 ROI confidence: `0.5127`
- Median ROI contrast: `39.34`
- Median ROI sharpness: `3.39`
- Low-quality samples: `1`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
