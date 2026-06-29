# Fixed Display Batch Report

Generated UTC: `2026-06-25T18:35:44+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/camera_sweep_20260625T183448Z/manual_bright`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/camera_sweep_20260625T183448Z/manual_bright/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 8
- Splits: {'train': 7, 'validation': 1}
- Temperature label: `30C`
- Temperature Celsius: `30.0`
- Humidity percent: `44`
- Minimum ROI confidence: `0.0458`
- Median ROI confidence: `0.5163`
- P10 ROI confidence: `0.5145`
- Median ROI contrast: `38.87`
- Median ROI sharpness: `3.36`
- Low-quality samples: `1`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
