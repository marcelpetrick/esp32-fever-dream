# Full Recognition Quality Loop

Date: 2026-07-21

Goal: ship a fixed-display recognizer that works across the observed image
conditions, not just on one convenient capture domain.

## Current state from recent commits

- `0bbbc443` trained a stronger CNN (16/32 conv filters, 64 dense units,
  dropout, class-balanced sample weights) and reported 94.15% real validation
  digit accuracy.
- `b99f5964` added `documents/dataset_review_20260629.html`, a useful static
  visual comparison of representative capture conditions.
- The current worktree contains uncommitted dataset changes only:
  `http_300_aqs_20260626T2040Z/labels_environment.csv` timestamp churn and
  expanded `live_surveillance_20260629T1003Z` proposal/queue/promoted-label
  files.
- The biggest remaining risk is label provenance. The large new promoted label
  files are bulk-approved OCR output, while the review queues still show all
  rows pending. That is useful for experiment training, but not enough by itself
  for deployment-quality accuracy claims.

## Label all data

For every capture batch:

1. Audit image quality first. Reject frames where display localization fails,
   brightness/contrast/sharpness are outside thresholds, or the frame is not a
   valid 640x480 JPEG.
2. Generate Ollama OCR proposals into `labels_ollama_proposals.csv`.
3. Prepare `labels_ollama_review_queue.csv`.
4. Promote only rows that are approved or corrected. Rows with quality failures
   stay out of `labels_environment.csv`.
5. Keep the reviewer provenance explicit:
   - `human` or a named person for row-level checked labels.
   - `owner-bulk-approved` only when a human intentionally bulk-accepts a set.
   - `auto-*` for automated promotion; these rows are rejected by training.

Verifiable criteria:

- `python3 tools/dataset/summarize_labeling_status.py --markdown-out reports/labeling_status.md --json-out reports/labeling_status.json`
  shows zero proposal-only batches that are in the split policy.
- Every training/validation/test batch has promoted labels.
- Review queues for deployment data either have zero pending rows or have a
  documented reason why remaining rows are excluded.

## Train/evaluate loop

1. Run the dataset status report.
2. Run `scripts/train_model.sh` with all promoted label files covered by the
   frozen split policy.
3. Require strict audit pass before treating a model as valid.
4. Evaluate both digit-level TFLite accuracy and full-reading accuracy.
5. Run the deployment gate before exporting/flashing firmware.

Minimum model-quality criteria before deployment:

- Strict dataset audit passes.
- Validation digit accuracy >= 98%.
- Frozen test digit accuracy >= 97%.
- Full-reading accepted accuracy >= 95% at the firmware confidence threshold.
- Per-digit accuracy >= 95% for every digit that appears at least 20 times in
  validation/test.
- Negative/ambiguous examples exist and false accepts are zero.
- The model remains within the configured firmware size and tensor-arena budget.

## If accuracy is not good enough

Run these in order, measuring each change against the same frozen validation and
test splits:

1. Fix labels: inspect confusion clusters and correct wrong OCR labels.
2. Fix crops: review misclassified digit crops and display-localization failures.
3. Improve capture conditions: collect more frames for lighting/exposure/focus
   domains that underperform.
4. Tune model training: sweep seeds, real-weight, epochs, dropout, and class
   weights.
5. Change architecture only if data/crop quality is no longer the bottleneck:
   try a small residual CNN or depthwise-separable CNN while keeping the TFLite
   model under 150 KB.

## Loop exit

The loop is done only when the deployment gate passes and the checked-in reports
show the exact label set, split policy, training parameters, validation/test
metrics, and firmware artifact used.
