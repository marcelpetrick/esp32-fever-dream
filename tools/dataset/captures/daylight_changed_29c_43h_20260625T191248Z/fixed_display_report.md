# Fixed Display Batch Report

Generated UTC: `2026-06-25T19:13:34+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/daylight_changed_29c_43h_20260625T191248Z`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/daylight_changed_29c_43h_20260625T191248Z/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 30
- Splits: {'test': 3, 'train': 24, 'validation': 3}
- Temperature label: `29C`
- Temperature Celsius: `29.0`
- Humidity percent: `43`
- Minimum ROI confidence: `0.0301`
- Median ROI confidence: `0.5225`
- P10 ROI confidence: `0.5123`
- Median ROI contrast: `39.42`
- Median ROI sharpness: `3.36`
- Low-quality samples: `1`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
