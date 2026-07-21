# TinyML Dataset Audit

Generated UTC: `2026-07-21T18:36:52+00:00`
Labels CSV: `/home/mpetrick/repos/esp32-fever-dream/models/generated/digit_dataset/merged_labels.csv`
Status: `pass`

## Requirements

- Minimum valid captures: 300
- Minimum distinct readings: 10
- Minimum held-out validation/test captures: 50
- Minimum validation captures: 50
- Minimum independent test captures: 0
- Minimum negative/ambiguous captures: 0
- Minimum samples per digit: 20
- Required digits: `0123456789`

## Checks

- minimum_captures: pass
- distinct_readings: pass
- all_digits_present: pass
- samples_per_digit: pass
- heldout_samples: pass
- minimum_validation: pass
- minimum_test: pass
- minimum_negative: pass
- validation_all_digits: pass
- test_all_digits: pass
- all_labels_trusted: pass
- split_names_valid: pass
- sample_ids_unique: pass
- images_split_exclusive: pass
- capture_batches_split_exclusive: pass
- all_images_hashable: pass
- perceptual_clusters_split_exclusive: pass

## Summary

- Rows: 1314
- Valid rows: 1314
- Usable localized rows: 1314
- Untrusted rows excluded: 0
- Negative/ambiguous rows: 0
- Distinct readings: 337
- Held-out rows: 355
- Splits: `{'test': 138, 'train': 959, 'validation': 217}`
- Digit counts: `{'0': 6868, '1': 816, '2': 2381, '3': 1077, '4': 2110, '5': 1625, '6': 1117, '7': 1573, '8': 2330, '9': 1127}`
- Split digit counts: `{'train': {'0': 5018, '1': 595, '2': 1729, '3': 795, '4': 1553, '5': 1198, '6': 823, '7': 1173, '8': 1658, '9': 802}, 'validation': {'0': 1131, '1': 134, '2': 396, '3': 171, '4': 349, '5': 275, '6': 187, '7': 288, '8': 369, '9': 172}, 'test': {'0': 719, '1': 87, '2': 256, '3': 111, '4': 208, '5': 152, '6': 107, '7': 112, '8': 303, '9': 153}}`
- Validation missing digits: `[]`
- Test missing digits: `[]`
- Missing digits: `[]`
- Underrepresented digits: `{}`
- Duplicate sample IDs: `[]`
- Cross-split images: `[]`
- Cross-split capture batches: `[]`
- Image/hash failures: 0
- Image/hash failure examples: `[]`
- Cross-split perceptual near-duplicates detected (report capped at 100): 0
- Cross-split near-duplicate examples: `[]`
- Sample readings: `['co2_ppm=1218 hcho_raw=135 tvoc_raw=375 28C 49%', 'co2_ppm=1229 hcho_raw=136 tvoc_raw=380 28C 49%', 'co2_ppm=1498 hcho_raw=185 tvoc_raw=58 28C 50%', 'co2_ppm=1498 hcho_raw=85 tvoc_raw=58 28C 53%', 'co2_ppm=1575 hcho_raw=235 tvoc_raw=658 28C 50%', 'co2_ppm=1581 hcho_raw=239 tvoc_raw=669 28C 50%', 'co2_ppm=1586 hcho_raw=242 tvoc_raw=677 28C 50%', 'co2_ppm=1592 hcho_raw=246 tvoc_raw=688 28C 50%', 'co2_ppm=1597 hcho_raw=246 tvoc_raw=688 28C 50%', 'co2_ppm=1603 hcho_raw=253 tvoc_raw=708 28C 50%', 'co2_ppm=1647 hcho_raw=285 tvoc_raw=789 28C 50%', 'co2_ppm=1680 hcho_raw=303 tvoc_raw=88 28C 51%', 'co2_ppm=1685 hcho_raw=303 tvoc_raw=88 28C 51%', 'co2_ppm=1685 hcho_raw=307 tvoc_raw=859 28C 51%', 'co2_ppm=1702 hcho_raw=38 tvoc_raw=890 28C 51%', 'co2_ppm=1702 hcho_raw=38 tvoc_raw=898 28C 51%', 'co2_ppm=1707 hcho_raw=32 tvoc_raw=890 28C 51%', 'co2_ppm=1713 hcho_raw=325 tvoc_raw=90 28C 51%', 'co2_ppm=1713 hcho_raw=329 tvoc_raw=92 28C 51%', 'co2_ppm=1724 hcho_raw=332 tvoc_raw=90 28C 51%']`

## Next Actions

- Capture more real images only when values have changed or lighting conditions are intentionally varied.
- Collect readings until every digit 0-9 appears at least 20 times.
- Keep at least 50 validation/test frames out of tuning.
- Add negative examples before trusting false-accept rates.
