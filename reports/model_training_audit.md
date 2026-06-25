# TinyML Dataset Audit

Generated UTC: `2026-06-25T18:47:05+00:00`
Labels CSV: `tools/dataset/captures/training_baseline_manual_20260625T183552Z/labels_environment.csv`
Status: `blocked`

## Requirements

- Minimum valid captures: 300
- Minimum distinct readings: 10
- Minimum held-out validation/test captures: 50
- Minimum samples per digit: 20
- Required digits: `0123456789`

## Checks

- minimum_captures: fail
- distinct_readings: fail
- all_digits_present: fail
- samples_per_digit: fail
- heldout_samples: fail

## Summary

- Rows: 100
- Valid rows: 100
- Distinct readings: 1
- Held-out rows: 20
- Splits: `{'test': 10, 'train': 80, 'validation': 10}`
- Digit counts: `{'2': 100, '3': 100, '4': 100, '9': 100}`
- Missing digits: `['0', '1', '5', '6', '7', '8']`
- Underrepresented digits: `{'0': 0, '1': 0, '5': 0, '6': 0, '7': 0, '8': 0}`
- Sample readings: `['29C 43%']`

## Next Actions

- Capture more real images only when values have changed or lighting conditions are intentionally varied.
- Collect readings until every digit 0-9 appears at least 20 times.
- Keep at least 50 validation/test frames out of tuning.
- Add negative examples before trusting false-accept rates.
