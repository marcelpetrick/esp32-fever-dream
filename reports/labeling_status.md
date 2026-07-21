# Labeling Status

Capture root: `tools/dataset/captures`

## Totals

- Images: 2914
- Promoted label rows: 2307
- Trusted-like valid label rows: 2307
- OCR proposal rows: 2467
- Review queue rows: 2467
- Pending review rows: 2467

## Batches

| Batch | Images | Labels | Trusted-like | Proposals | Pending review | Reviewer kinds |
|---|---:|---:|---:|---:|---:|---|
| approved_29c_43h_20260625T185939Z | 41 | 40 | 40 | 0 | 0 | `{'missing': 40}` |
| baseline_20260625T182247Z | 10 | 0 | 0 | 0 | 0 | `{}` |
| baseline_20260625T182331Z | 104 | 100 | 100 | 0 | 0 | `{'missing': 100}` |
| camera_sweep_20260625T182850Z | 0 | 0 | 0 | 0 | 0 | `{}` |
| camera_sweep_20260625T182911Z | 0 | 0 | 0 | 0 | 0 | `{}` |
| camera_sweep_20260625T183448Z | 0 | 0 | 0 | 0 | 0 | `{}` |
| checks | 0 | 0 | 0 | 0 | 0 | `{}` |
| daylight_changed_29c_43h_20260625T191248Z | 32 | 30 | 30 | 0 | 0 | `{'missing': 30}` |
| http_300_aqs_20260626T2040Z | 306 | 13 | 13 | 300 | 300 | `{'bulk': 13}` |
| live_mounted_29c_41h_20260625T195058Z | 23 | 20 | 20 | 0 | 0 | `{'missing': 20}` |
| live_surveillance_20260629T1003Z | 1647 | 1485 | 1485 | 1647 | 1647 | `{'bulk': 1485}` |
| live_upright_20260626T2309Z | 3 | 3 | 3 | 0 | 0 | `{'missing': 3}` |
| live_validation_20260625T193948Z | 2 | 0 | 0 | 0 | 0 | `{}` |
| serial20260626 | 93 | 0 | 0 | 0 | 0 | `{}` |
| serial_20260626T130547Z | 0 | 0 | 0 | 0 | 0 | `{}` |
| serial_20260626T130756Z | 0 | 0 | 0 | 0 | 0 | `{}` |
| serial_20260626T131502Z | 0 | 0 | 0 | 0 | 0 | `{}` |
| serial_20260626T131715Z | 0 | 0 | 0 | 0 | 0 | `{}` |
| serial_20260626T131912Z | 1 | 0 | 0 | 0 | 0 | `{}` |
| serial_timed_20260627T1200Z | 6 | 0 | 0 | 0 | 0 | `{}` |
| serial_timed_fast_20260627T1205Z | 520 | 496 | 496 | 520 | 520 | `{'bulk': 496}` |
| stability_20260625T183410Z | 21 | 20 | 20 | 0 | 0 | `{'missing': 20}` |
| timed_upright_20260627T1115Z | 4 | 0 | 0 | 0 | 0 | `{}` |
| training_baseline_manual_20260625T183552Z | 101 | 100 | 100 | 0 | 0 | `{'missing': 100}` |

## Labeling rule

- `labels_ollama_proposals.csv` is OCR output, not ground truth.
- `labels_ollama_review_queue.csv` is the review worklist.
- `labels_environment.csv` is trainable only when rows are approved/corrected with non-automated reviewer provenance.
- `bulk` reviewer provenance is allowed for experiments but must be backed by spot-check reports before deployment qualification.
