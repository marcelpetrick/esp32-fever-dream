# TinyML Dataset Audit

Generated UTC: `2026-06-26T07:39:51+00:00`
Labels CSV: `tools/dataset/captures/live_mounted_29c_41h_20260625T195058Z/labels_environment.csv`
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

- Rows: 20
- Valid rows: 20
- Distinct readings: 1
- Held-out rows: 4
- Splits: `{'test': 2, 'train': 16, 'validation': 2}`
- Digit counts: `{'1': 20, '2': 20, '4': 20, '9': 20}`
- Missing digits: `['0', '3', '5', '6', '7', '8']`
- Underrepresented digits: `{'0': 0, '3': 0, '5': 0, '6': 0, '7': 0, '8': 0}`
- Sample readings: `['29C 41%']`

## Next Actions

- Capture more real images only when values have changed or lighting conditions are intentionally varied.
- Collect readings until every digit 0-9 appears at least 20 times.
- Keep at least 50 validation/test frames out of tuning.
- Add negative examples before trusting false-accept rates.
