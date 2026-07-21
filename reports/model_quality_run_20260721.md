# Model quality run - 2026-07-21

This run tested the automation-only remediation path after adding consensus
labels, corrected CO2 semantics, and generated negative examples.

## Inputs

- Positive labels:
  - `tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment_auto_consensus.csv`
  - `tools/dataset/captures/live_surveillance_20260629T1003Z/labels_environment_auto_consensus.csv`
- Negative labels:
  - `tools/dataset/captures/generated_negative_20260721/labels_environment.csv`
- Training command:

```sh
./scripts/train_model.sh \
  --labels tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment_auto_consensus.csv \
  --labels tools/dataset/captures/live_surveillance_20260629T1003Z/labels_environment_auto_consensus.csv \
  --labels tools/dataset/captures/generated_negative_20260721/labels_environment.csv \
  --epochs 60 --real-weight 3 --qualify-test --export-firmware-header
```

## Result

The retrained model is not deployable and must not replace the checked-in model.

- TFLite size: 83,960 bytes.
- Validation digit accuracy: 83.47%.
- Frozen test digit accuracy: 82.05%.
- Full-frame raw digit accuracy: 84.87%.
- Full-reading exact accuracy after corrected CO2 confidence handling: 29.05%.
- Positive rejection rate: 20.23%.
- Generated negative rows: 120.
- False accepts: 7.
- False-accept rate: 5.83%.

Field-level raw accuracy:

| Field | Accuracy |
| --- | ---: |
| CO2 | 34.75% |
| HCHO | 66.92% |
| TVOC | 66.39% |
| Temperature | 98.17% |
| Humidity | 87.07% |

## Decision

Reject the trained artifacts. The source/data changes are still useful:

- CO2 is now modeled as left-aligned 3- or 4-digit text instead of zero-padded
  text.
- Host and firmware confidence calculations now ignore the unused fourth CO2
  box for 3-digit CO2 readings.
- Generated negative examples are available for false-accept measurement.

## Next loop

Do not run more blind training on the current single-model consensus labels.
Improve label quality first:

1. Generate independent `llama3.2-vision:11b` proposals for the AQS batches.
2. Optionally add `minicpm-v` proposals for disagreements.
3. Regenerate consensus with exact multi-model agreement.
4. Add automated crop-quality filters for pollutant rows.
5. Retrain only when labels/crops change, then re-run
   `./scripts/verify_model_deployment.sh`.
