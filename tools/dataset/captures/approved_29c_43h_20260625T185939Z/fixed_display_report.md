# Fixed Display Batch Report

Generated UTC: `2026-06-25T19:00:35+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/approved_29c_43h_20260625T185939Z`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/approved_29c_43h_20260625T185939Z/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 40
- Splits: {'test': 4, 'train': 32, 'validation': 4}
- Temperature label: `29C`
- Temperature Celsius: `29.0`
- Humidity percent: `43`
- Minimum ROI confidence: `0.4944`
- Median ROI confidence: `0.4985`
- P10 ROI confidence: `0.4952`
- Median ROI contrast: `37.92`
- Median ROI sharpness: `3.08`
- Low-quality samples: `0`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
