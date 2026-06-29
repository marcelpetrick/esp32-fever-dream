# Model Quality Remediation Plan

Last updated: 2026-06-29.

## Goal

Resolve the labeling, dataset, evaluation, and training defects through gated
iterations. Each iteration follows: reproduce, implement one bounded fix, test,
regenerate evidence, and commit. The deployed model remains unchanged until
every production gate passes.

## Baseline

- The timed corpus contains 520 unique captures; 501 pass the current image
  quality and localization audit.
- The Ollama label file contained 44 rows and 37 valid proposals at review time.
- All digits occur in the proposals, but confirmed transcription errors include
  missing leading digits and a humidity value of `6` instead of `46`.
- The deployed model achieved 18.4% per-digit accuracy and zero complete
  five-field matches on the valid proposal snapshot.
- An isolated experiment using fresh real crops improved held-out per-digit
  accuracy from 21.9% to 59.4%, but still produced zero complete held-out
  readings. These proposal-derived figures are directional only.
- The current mixed synthetic/real test report of 97.75% is not production
  evidence.

## Work Sequence

### 1. Document and commit this plan

- Commit this document alone as
  `docs(ml): add model quality remediation plan`.
- Gate: documentation and static checks pass, the worktree is otherwise clean,
  and this document contains every criterion below.

### 2. Stabilize the Ollama labeler

- Preserve the current CSV and log, then gracefully stop the inefficient run.
- Require structured JSON output, cap generation at 96 tokens, enforce a
  300-second total request deadline, bound retries, and record model/prompt
  provenance.
- Resume successful rows but retry error rows. Make `--no-resume` replace output
  atomically instead of appending duplicates.
- Provide functional duplicate-policy flags and validate split fractions.
- Gate: unit tests cover deadlines, malformed streams, retries, resume,
  overwrite, duplicate IDs, and split validation; a 20-frame smoke run has no
  request over 300 seconds and resumes without losing successes.

### 3. Separate proposals from ground truth

- Write automation to `labels_ollama_proposals.csv`. Reserve
  `labels_environment.csv` for reviewed truth.
- Generate a review queue with proposed values, temporal neighbors, image
  quality, decisions, corrections, reviewer, review time, model, and prompt
  version.
- Add structural and temporal checks for missing leading digits, implausible
  jumps, incorrect widths, and outliers.
- Gate: known errors in captures `0050`, `0832`, `0021`, and `1014` are detected
  or corrected; all validation/test labels are reviewed; pending proposals are
  rejected by training; a random 10% audit has zero errors or the affected
  temporal cluster is fully reviewed.

### 4. Harden corpus and split integrity

- Exclude frames failing decode, localization, brightness, contrast, or
  sharpness checks and cluster perceptual duplicates before splitting.
- Split by independent capture session. Temporal blocks may only divide
  training data; no perceptual cluster may cross splits.
- Generate dynamic coverage reports instead of hard-coded limitations.
- Gate: no rejected image or duplicate cluster enters conflicting splits;
  training has at least 300 reviewed frames, 10 readings, and 20 real samples
  per digit; validation has at least 50 reviewed frames; test has at least 100
  reviewed frames, 10 readings, and every digit; the negative/ambiguous set has
  at least 50 frames.

### 5. Verify crop and preprocessing correctness

- Generate review contact sheets for every field/position and locator failure.
- Add golden-image tests for display localization and all 16 digit ROIs.
- Compare firmware input tensors byte-for-byte with host preprocessing and use
  one resize, contrast, and quantization path everywhere.
- Gate: every golden crop contains the complete intended digit; host and
  firmware tensors match on at least 20 frames; locator success is at least 99%
  on accepted images and failures are rejected rather than processed with
  fallback coordinates.

### 6. Make evaluation honest

- Report real and synthetic metrics separately for each split.
- Permit synthetic samples only in training.
- Report per-digit confusion, per-field exact accuracy, complete five-field
  accuracy, confidence calibration, false-accept rate, and rejection rate from
  the quantized TFLite artifact.
- Freeze the test manifest and prevent tuning runs from reading test labels.
- Gate: the deployed baseline is reproducible on frozen real validation/test
  sets; every headline metric is real-only; tests fail on synthetic held-out
  rows or split leakage.

### 7. Improve training iteratively

- Use class-balanced real sampling and cap synthetic data at a 1:1 ratio to real
  training crops.
- Compare real weighting factors 1x, 3x, and 5x using validation only, add early
  stopping, and run candidates with three fixed seeds.
- In each loop, address the largest real validation confusion with one bounded
  data, preprocessing, or model change. Do not read frozen test results until a
  candidate passes validation.
- Validation and final-test gates: at least 99% per-digit accuracy, 98% complete
  five-field accuracy, at most 1% false accepts, and no digit below 97%. Final
  gates must hold across all three seeds without a regression above one
  percentage point.

### 8. Deploy only after final acceptance

- Export the winning int8 model reproducibly, remove prototype corrections,
  restore the intended confidence threshold, and run all repository checks.
- Verify model size at most 150 KB, capture plus inference at most 60 seconds,
  host/device prediction parity, and live shadow accuracy before promotion.
- Commit the generated model, evaluation evidence, firmware integration, and
  version bump only after the complete gate passes.

## Resolution Loop

For every unresolved gate:

1. Record the failing metric and reproduction command below.
2. Select the highest-impact single failure.
3. Implement the smallest bounded correction.
4. Run focused tests, then the phase gate.
5. Regenerate evidence and compare it with the previous committed baseline.
6. Commit only measurable improvements without regressions; otherwise revert
   the experiment and record the outcome.
7. Repeat until all gates pass, then advance.

## Iteration Log

| Iteration | Gate | Baseline | Change | Result | Commit |
| --- | --- | --- | --- | --- | --- |
| 0 | Plan recorded | No consolidated remediation plan | Added this plan | Passed documentation checks | `b9f0acf` |
| 1 | Bounded proposals | Requests reached 1,802 seconds and error rows were skipped | Added structured bounded requests and atomic retryable proposals | Unit and smoke persistence tests pass | `7bc97dd` |
| 2 | Trusted labels | Ollama rows were accepted as truth | Added review queues, provenance, anomaly flags, and training rejection | Four known bad labels flagged; 45 rows pending review | `a0fe992` |
| 3 | Dataset integrity | Synthetic metrics and capture leakage inflated results | Added independent-batch, trust, coverage, and firmware preprocessing gates | Current corpus correctly blocked | `247ecee` |
| 4 | Honest qualification | Mixed synthetic test reported 97.75% | Added real-only int8 validation, seed/weight sweep, and frozen-test controls | Smoke training passes; deployment remains blocked | `1980354` |
| 5 | Labeler reliability | Structured Qwen output and response-owned sockets were not handled | Added bounded response-socket reads and Qwen structured fallback | 20/20 smoke frames finished; maximum 2.8 seconds | `4d298a7` |
| 6 | Deployment safety | Prototype preprocessing and controls could be exported without evidence | Shared firmware preprocessing and added a strict deployment gate | Host/firmware builds pass; current deployment blocked | `b90b76c` |

Current blocking evidence is in `reports/model_deployment_gate.json`. It must
remain blocked until reviewed independent validation/test data exists and the
prototype firmware controls can be removed based on measured results.

## Fixed Assumptions

- Ollama output is an untrusted proposal until human approval.
- Synthetic data is training-only.
- The active labeler may be stopped after preserving its output and logs.
- The frozen test set is evaluated only for final candidate qualification.
- Production thresholds are 99% per-digit, 98% full-reading, and at most 1%
  false accepts.
- Each completed iteration is a separate reviewable commit.
