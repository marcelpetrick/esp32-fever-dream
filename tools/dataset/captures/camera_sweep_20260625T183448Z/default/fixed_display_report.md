# Fixed Display Batch Report

Generated UTC: `2026-06-25T18:35:00+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/camera_sweep_20260625T183448Z/default`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/camera_sweep_20260625T183448Z/default/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 8
- Splits: {'train': 7, 'validation': 1}
- Temperature label: `30C`
- Temperature Celsius: `30.0`
- Humidity percent: `44`
- Minimum ROI confidence: `0.0944`
- Median ROI confidence: `0.2180`
- P10 ROI confidence: `0.1024`
- Median ROI contrast: `14.88`
- Median ROI sharpness: `1.30`
- Low-quality samples: `7`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
