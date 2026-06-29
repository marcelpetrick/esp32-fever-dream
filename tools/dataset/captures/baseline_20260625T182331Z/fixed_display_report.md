# Fixed Display Batch Report

Generated UTC: `2026-06-25T18:28:13+00:00`
Source directory: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/baseline_20260625T182331Z`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/tools/dataset/captures/baseline_20260625T182331Z/labels_environment.csv`
Method: human-confirmed fixed-layout baseline labels plus ROI quality metrics

## Summary

- Rows: 100
- Splits: {'test': 10, 'train': 80, 'validation': 10}
- Temperature label: `30C`
- Temperature Celsius: `30.0`
- Humidity percent: `44`
- Minimum ROI confidence: `0.0907`
- Median ROI confidence: `0.1555`
- P10 ROI confidence: `0.0956`
- Median ROI contrast: `10.08`
- Median ROI sharpness: `0.89`
- Low-quality samples: `97`

## Limitations

- All baseline labels have the same temperature and humidity values.
- The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.
- A useful TinyML digit classifier still needs captures where the displayed values vary.
