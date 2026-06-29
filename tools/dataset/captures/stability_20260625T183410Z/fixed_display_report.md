# Fixed Display Batch Report

Generated UTC: `2026-06-25T18:34:36+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/stability_20260625T183410Z`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/stability_20260625T183410Z/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 20
- Splits: {'test': 2, 'train': 16, 'validation': 2}
- Temperature label: `30C`
- Temperature Celsius: `30.0`
- Humidity percent: `44`
- Minimum ROI confidence: `0.0889`
- Median ROI confidence: `0.1058`
- P10 ROI confidence: `0.0921`
- Median ROI contrast: `6.27`
- Median ROI sharpness: `0.53`
- Low-quality samples: `19`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
