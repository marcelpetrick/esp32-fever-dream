# TinyML Dataset Audit

Generated UTC: `2026-06-26T21:17:10+00:00`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/models/generated/digit_dataset/merged_labels.csv`
Status: `blocked`

## Requirements

- Minimum valid captures: 300
- Minimum distinct readings: 10
- Minimum held-out validation/test captures: 50
- Minimum samples per digit: 20
- Required digits: `0123456789`

## Checks

- minimum_captures: pass
- distinct_readings: fail
- all_digits_present: fail
- samples_per_digit: fail
- heldout_samples: pass

## Summary

- Rows: 353
- Valid rows: 353
- Distinct readings: 5
- Held-out rows: 67
- Splits: `{'test': 31, 'train': 286, 'validation': 36}`
- Digit counts: `{'0': 160, '1': 20, '2': 191, '3': 332, '4': 513, '9': 190}`
- Missing digits: `['5', '6', '7', '8']`
- Underrepresented digits: `{'5': 0, '6': 0, '7': 0, '8': 0}`
- Sample readings: `['29C 41%', '29C 43%', '30C 44%', '42%', '43%']`

## Next Actions

- Capture more real images only when values have changed or lighting conditions are intentionally varied.
- Collect readings until every digit 0-9 appears at least 20 times.
- Keep at least 50 validation/test frames out of tuning.
- Add negative examples before trusting false-accept rates.
