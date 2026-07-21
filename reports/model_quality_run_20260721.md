# Model Quality Run - 2026-07-21

This records the autonomous labeling/OCR cleanup and training loop run on 2026-07-21.

## Data actions

- Removed 60 promoted `live_surveillance_20260629T1003Z` rows whose image paths could not be resolved by the training dataset builder.
- Removed temporal-anomaly OCR labels before training:
  - `serial_timed_fast_20260627T1205Z`: 103 rows removed, 393 retained.
  - `live_surveillance_20260629T1003Z`: 503 rows removed, 922 retained.
- Restricted the frozen policy to AQS-layout captures only. Legacy two-field captures remain useful for reference, but are excluded from this training policy because their layout does not match the current firmware recognizer.
- Added interleaved split support so long capture runs can contribute train/validation/test examples without putting entire lighting/time domains into only one split.

## Model/code actions

- Corrected CO2 and humidity digit crop boxes in both host-side dataset generation and firmware inference.
- Increased the digit classifier capacity while keeping the exported int8 model below the deployment size limit.
- Added crop-level mistake mining:
  - `reports/digit_crop_mistakes.csv`
  - `reports/digit_crop_mistakes_summary.json`
  - `reports/digit_mistake_sheets/*.png`

## Training command

```sh
./scripts/train_model.sh \
  --labels tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment.csv \
  --labels tools/dataset/captures/live_surveillance_20260629T1003Z/labels_environment.csv \
  --epochs 60 \
  --real-weight 3 \
  --qualify-test \
  --export-firmware-header
```

## Current metrics

- TFLite model size: 83,480 bytes.
- Validation crop accuracy: 88.25%.
- Test crop accuracy: 86.68%.
- Worst test digit: digit `3` at 76.58%.
- Full-frame digit accuracy: 89.82%.
- Full-reading exact accuracy: 12.78%.
- Positive rejection rate at current firmware threshold: 85.32%.
- Negative examples: 0.
- Deployment gate: blocked.

## Blockers

The current model is not production-ready. More training on the current labels alone is unlikely to close the gap.

Blocking issues:

1. Bulk OCR labels are still not human-reviewed ground truth.
2. Gas fields need explicit leading-blank handling. Treating blank leading digits as ordinary zeros creates misleading training examples and field-level failures.
3. CO2/TVOC/HCHO exact field accuracy is still too low after crop-box correction.
4. No negative/ambiguous frame set exists, so false-accept behavior cannot be measured.
5. Firmware still uses the low prototype confidence threshold and the prototype humidity correction path.

## Verifiable next loop

1. Review and correct the highest-value rows from `reports/digit_crop_mistakes.csv`, prioritizing high-confidence errors and positions `co2_3`, `co2_2`, `tvoc_1`, `hcho_3`, `tvoc_2`, `hcho_2`, and `humidity_1`.
2. Add a supported representation for leading blanks in gas fields. Verifiable criterion: blank-leading gas displays do not create digit-label rows for invisible digits, or a dedicated blank class/heuristic is evaluated separately.
3. Add at least 100 negative/ambiguous frames. Verifiable criterion: `reports/model_deployment_gate.json` reports `negative_set_present: true` and a measured false-accept rate.
4. Retrain and require:
   - test digit accuracy >= 95%;
   - worst-digit test accuracy >= 90%;
   - full-reading exact accuracy >= 95%;
   - model size <= 110 KB;
   - deployment gate passes.
