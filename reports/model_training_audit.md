# TinyML Dataset Audit

Generated UTC: `2026-06-29T17:01:44+00:00`
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

- Rows: 1850
- Valid rows: 1850
- Usable localized rows: 1820
- Untrusted rows excluded: 0
- Negative/ambiguous rows: 0
- Distinct readings: 679
- Held-out rows: 1400
- Splits: `{'test': 1261, 'train': 420, 'validation': 139}`
- Digit counts: `{'0': 9168, '1': 1447, '2': 3314, '3': 1327, '4': 2628, '5': 2141, '6': 1510, '7': 2088, '8': 3166, '9': 1611}`
- Split digit counts: `{'train': {'0': 2208, '1': 270, '2': 705, '3': 388, '4': 661, '5': 621, '6': 422, '7': 618, '8': 412, '9': 175}, 'validation': {'0': 498, '1': 98, '2': 139, '3': 40, '4': 335, '5': 180, '6': 20, '7': 393, '9': 41}, 'test': {'0': 6462, '1': 1079, '2': 2470, '3': 899, '4': 1632, '5': 1340, '6': 1068, '7': 1077, '8': 2754, '9': 1395}}`
- Validation missing digits: `['8']`
- Test missing digits: `[]`
- Missing digits: `[]`
- Underrepresented digits: `{}`
- Duplicate sample IDs: `[]`
- Cross-split images: `[]`
- Cross-split capture batches: `[]`
- Image/hash failures: 30
- Image/hash failure examples: `['live_surveillance_20260629T1003Z_capture_0083:display_not_found', 'live_surveillance_20260629T1003Z_capture_0163:display_not_found', 'live_surveillance_20260629T1003Z_capture_0829:display_not_found', 'live_surveillance_20260629T1003Z_capture_1186:display_not_found', 'live_surveillance_20260629T1003Z_capture_1494:display_not_found', 'live_surveillance_20260629T1003Z_capture_1502:display_not_found', 'live_surveillance_20260629T1003Z_capture_1553:display_not_found', 'live_surveillance_20260629T1003Z_capture_1557:display_not_found', 'live_surveillance_20260629T1003Z_capture_1559:display_not_found', 'live_surveillance_20260629T1003Z_capture_1563:display_not_found', 'live_surveillance_20260629T1003Z_capture_1564:display_not_found', 'live_surveillance_20260629T1003Z_capture_1568:display_not_found', 'live_surveillance_20260629T1003Z_capture_1570:display_not_found', 'live_surveillance_20260629T1003Z_capture_1575:display_not_found', 'live_surveillance_20260629T1003Z_capture_1577:display_not_found', 'live_surveillance_20260629T1003Z_capture_1578:display_not_found', 'live_surveillance_20260629T1003Z_capture_1579:display_not_found', 'live_surveillance_20260629T1003Z_capture_1580:display_not_found', 'live_surveillance_20260629T1003Z_capture_1586:display_not_found', 'live_surveillance_20260629T1003Z_capture_1587:display_not_found']`
- Cross-split perceptual near-duplicates detected (report capped at 100): 0
- Cross-split near-duplicate examples: `[]`
- Sample readings: `['29C 41%', '29C 43%', 'co2_ppm=1002 hcho_raw=13 tvoc_raw=36 28C 49%', 'co2_ppm=1119 hcho_raw=15 tvoc_raw=36 28C 49%', 'co2_ppm=1218 hcho_raw=135 tvoc_raw=375 28C 49%', 'co2_ppm=1229 hcho_raw=136 tvoc_raw=380 28C 49%', 'co2_ppm=1234 hcho_raw=13 tvoc_raw=383 28C 49%', 'co2_ppm=1234 hcho_raw=13 tvoc_raw=386 28C 49%', 'co2_ppm=1273 hcho_raw=144 tvoc_raw=403 28C 49%', 'co2_ppm=1278 hcho_raw=146 tvoc_raw=408 28C 49%', 'co2_ppm=1278 hcho_raw=15 tvoc_raw=406 28C 49%', 'co2_ppm=1278 hcho_raw=45 tvoc_raw=406 28C 49%', 'co2_ppm=1278 hcho_raw=47 tvoc_raw=44 28C 49%', 'co2_ppm=1284 hcho_raw=144 tvoc_raw=406 28C 49%', 'co2_ppm=1284 hcho_raw=147 tvoc_raw=406 28C 49%', 'co2_ppm=1284 hcho_raw=15 tvoc_raw=14 28C 49%', 'co2_ppm=1284 hcho_raw=18 tvoc_raw=14 28C 49%', 'co2_ppm=1289 hcho_raw=47 tvoc_raw=11 28C 49%', 'co2_ppm=1295 hcho_raw=13 tvoc_raw=11 28C 49%', 'co2_ppm=1322 hcho_raw=54 tvoc_raw=43 28C 50%']`

## Next Actions

- Capture more real images only when values have changed or lighting conditions are intentionally varied.
- Collect readings until every digit 0-9 appears at least 20 times.
- Keep at least 50 validation/test frames out of tuning.
- Add negative examples before trusting false-accept rates.
