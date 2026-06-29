# TinyML Dataset Audit

Generated UTC: `2026-06-29T05:43:57+00:00`
Labels CSV: `models/generated/digit_dataset/merged_labels.csv`
Status: `blocked`

## Requirements

- Minimum valid captures: 300
- Minimum distinct readings: 10
- Minimum held-out validation/test captures: 50
- Minimum validation captures: 50
- Minimum independent test captures: 100
- Minimum negative/ambiguous captures: 50
- Minimum samples per digit: 20
- Required digits: `0123456789`

## Checks

- minimum_captures: fail
- distinct_readings: fail
- all_digits_present: fail
- samples_per_digit: fail
- heldout_samples: fail
- minimum_validation: fail
- minimum_test: fail
- minimum_negative: fail
- validation_all_digits: fail
- test_all_digits: fail
- all_labels_trusted: pass
- split_names_valid: pass
- sample_ids_unique: pass
- images_split_exclusive: pass
- capture_batches_split_exclusive: pass
- all_images_hashable: fail
- perceptual_clusters_split_exclusive: pass

## Summary

- Rows: 353
- Valid rows: 353
- Usable localized rows: 108
- Untrusted rows excluded: 0
- Negative/ambiguous rows: 0
- Distinct readings: 6
- Held-out rows: 3
- Splits: `{'train': 105, 'validation': 3}`
- Digit counts: `{'0': 60, '1': 24, '2': 67, '3': 90, '4': 160, '6': 4, '7': 2, '9': 61}`
- Split digit counts: `{'train': {'0': 44, '1': 20, '2': 61, '3': 85, '4': 149, '9': 61}, 'validation': {'0': 16, '1': 4, '2': 6, '3': 5, '4': 11, '6': 4, '7': 2}, 'test': {}}`
- Validation missing digits: `['5', '8', '9']`
- Test missing digits: `['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']`
- Missing digits: `['5', '8']`
- Underrepresented digits: `{'5': 0, '6': 4, '7': 2, '8': 0}`
- Duplicate sample IDs: `[]`
- Cross-split images: `[]`
- Cross-split capture batches: `[]`
- Image/hash failures: 245
- Image/hash failure examples: `['baseline_20260625T182331Z_capture_0001:display_not_found', 'baseline_20260625T182331Z_capture_0002:display_not_found', 'baseline_20260625T182331Z_capture_0003:display_not_found', 'baseline_20260625T182331Z_capture_0005:display_not_found', 'baseline_20260625T182331Z_capture_0007:display_not_found', 'baseline_20260625T182331Z_capture_0013:display_not_found', 'baseline_20260625T182331Z_capture_0016:display_not_found', 'baseline_20260625T182331Z_capture_0018:display_not_found', 'baseline_20260625T182331Z_capture_0019:display_not_found', 'baseline_20260625T182331Z_capture_0021:display_not_found', 'baseline_20260625T182331Z_capture_0022:display_not_found', 'baseline_20260625T182331Z_capture_0025:display_not_found', 'baseline_20260625T182331Z_capture_0026:display_not_found', 'baseline_20260625T182331Z_capture_0027:display_not_found', 'baseline_20260625T182331Z_capture_0028:display_not_found', 'baseline_20260625T182331Z_capture_0029:display_not_found', 'baseline_20260625T182331Z_capture_0030:display_not_found', 'baseline_20260625T182331Z_capture_0032:display_not_found', 'baseline_20260625T182331Z_capture_0033:display_not_found', 'baseline_20260625T182331Z_capture_0035:display_not_found']`
- Cross-split perceptual near-duplicates detected (report capped at 100): 0
- Cross-split near-duplicate examples: `[]`
- Sample readings: `['29C 41%', '29C 43%', '30C 44%', 'co2_ppm=442 hcho_raw=12 tvoc_raw=30 26C 43%', 'co2_ppm=444 hcho_raw=13 tvoc_raw=36 27C 43%', 'co2_ppm=446 hcho_raw=17 tvoc_raw=41 26C 42%']`

## Next Actions

- Capture more real images only when values have changed or lighting conditions are intentionally varied.
- Collect readings until every digit 0-9 appears at least 20 times.
- Keep at least 50 validation/test frames out of tuning.
- Add negative examples before trusting false-accept rates.
