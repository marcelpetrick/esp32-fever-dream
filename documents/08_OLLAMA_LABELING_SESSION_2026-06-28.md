# Ollama Vision OCR Labeling Session — 2026-06-28

## What was done

A fully automated labeling pipeline was built, debugged, and run against the
520-frame timed capture batch (`serial_timed_fast_20260627T1205Z`).

### Tooling built

| Tool | Purpose |
|---|---|
| `tools/dataset/ollama_label_batch.py` | Queries a local Ollama vision model for each frame, extracts five AQS values, writes proposals CSV |
| `tools/model_training/tests/test_audit_dataset.py` | Tests for digit-counting fix in the audit |
| `tools/model_training/audit_dataset.py` | Fixed `row_label()` to count digits from all five AQS fields; added `trusted_label()` provenance gate |

### Key iterations on the labeler

| Commit | Change | Why |
|---|---|---|
| `58a9ac1` | Initial auto-labeler | Replace manual labeling |
| `0b2423b` | Switch model to qwen3-vl:4b, raise timeout to 360s | llama3.2-vision cold-start exceeded 120s limit causing queue backup |
| `0bf074e` | Add `num_ctx=2048` | Forces flash-attention + all 37 LLM layers onto A2000 GPU (was 29/41), total VRAM drops from 11.1→4.3 GiB |
| `557e587` | Random frame shuffle | Linear order kept CO2 stuck at 833–838 for 200+ frames; shuffle samples the full 107-min session immediately |
| `3818011` | Switch to streaming (`stream=true`) | `stream=false` caused socket timeout after 360s even during active inference; streaming resets the timer on every token |
| `62a58b3` | 30s cooldown before parse retries after HTTP 500 | Immediate parse retries after model eviction hit a reloading model 3× causing a 39-min single-frame stall |

### GPU / inference findings

- Hardware: NVIDIA RTX A2000 8GB Laptop GPU (confirmed via `/proc/driver/nvidia/`) + Intel Iris Xe
- `nvidia-smi` fails (NVML library 610.43 vs kernel module 595.71 mismatch) but CUDA compute works
- Without `num_ctx=2048`: 29/41 LLM layers on GPU, 12 on CPU, total 11.1 GiB → ~120–170s/frame with cascading timeout spikes
- With `num_ctx=2048`: flash attention enabled, 37/37 layers on GPU, 4.3 GiB VRAM → ~50–220s/frame (high variance driven by CLIP visual encoder, not LLM)
- Steady-state warm inference: ~50–160s; cold-start or model-eviction frames: up to 450s

## Labeling results

### Timed batch (`serial_timed_fast_20260627T1205Z`, 520 frames)

45 frames processed before session ended.

| Status | Count |
|---|---|
| `valid=true` proposals | **38** |
| `valid=false` (unreadable) | 7 |
| Failed / skipped | 0 |
| Remaining unlabeled | 475 |

Output file: `labels_ollama_proposals.csv` (+ `labels_ollama_review_queue.csv` for human review)

CO2 range captured: **574–838 ppm** across 14 distinct values,  
covering digits **5, 6, 7, 8** that were completely absent from prior batches.

## Digit coverage — trusted frames only

Trusted = human-confirmed baseline batches only (193 frames). The 38 timed
proposals are in the review queue and not yet counted.

| Digit | Trusted count | Status |
|---|---|---|
| 0 | 1 | ❌ need 19 more |
| 1 | 24 | ❌ need 4 more (marginal) |
| 2 | 199 | ✓ |
| 3 | 175 | ✓ |
| 4 | 201 | ✓ |
| 5 | 0 | ❌ entirely in proposals (not yet trusted) |
| 6 | 4 | ❌ mostly in proposals |
| 7 | 2 | ❌ mostly in proposals |
| 8 | 0 | ❌ entirely in proposals |
| 9 | 190 | ✓ |

**Once the 38 proposals are reviewed and approved**, the picture changes dramatically:

| Digit | Projected count | Status |
|---|---|---|
| 5 | ~34 | ✓ |
| 6 | ~40 | ✓ |
| 7 | ~46 | ✓ |
| 8 | ~49 | ✓ |
| 0 | ~4 | ❌ still need ~16 more |

## Remaining blockers for training

| Check | Current | Need | Gap |
|---|---|---|---|
| `minimum_captures` | 193 trusted | 300 | 107 more trusted frames |
| `heldout_samples` | 38 | 50 | 12 more |
| `distinct_readings` | 5 | 10 | 5 more distinct display values |
| `all_digits_present` | missing 5,6,7,8 (trusted) | all 0–9 | review proposals → clears |
| `samples_per_digit` digit 0 | 1 | 20 | needs CO2 x00 or HCHO/TVOC with 0 |
| `all_labels_trusted` | 38 untrusted proposals | 0 | human review of proposals |

## Next steps

1. **Human review** — open `labels_ollama_review_queue.csv`, verify a sample of
   the 38 proposals against the source images, set `review_decision` to
   `approved` or `rejected`.  The review queue includes quality flags
   (`display_not_found`, `brightness_too_low`, etc.) to prioritise which rows
   need the closest look.

2. **Continue labeling** — resume the timed run to cover the remaining 475
   frames.  With shuffle enabled, digit 0 should surface within ~20–30 frames
   (CO2 values containing a zero appear throughout the session).
   ```sh
   python3 tools/dataset/ollama_label_batch.py \
     --dataset-dir tools/dataset/captures/serial_timed_fast_20260627T1205Z \
     --model qwen3-vl:4b --num-ctx 2048 --shuffle \
     --lighting-label timed_daylight_usb
   ```

3. **Merge and retrain** — once all checks pass:
   ```sh
   bash scripts/train_model.sh \
     --labels tools/dataset/captures/approved_29c_43h_20260625T185939Z/labels_environment.csv \
     --labels tools/dataset/captures/training_baseline_manual_20260625T183552Z/labels_environment.csv \
     --labels tools/dataset/captures/daylight_changed_29c_43h_20260625T191248Z/labels_environment.csv \
     --labels tools/dataset/captures/live_mounted_29c_41h_20260625T195058Z/labels_environment.csv \
     --labels tools/dataset/captures/live_upright_20260626T2309Z/labels_environment.csv \
     --labels <approved-timed-run-labels>
   ```

4. **Acceptance criteria before flashing**
   - Per-digit accuracy ≥ 99% on held-out test set
   - Full five-value exact match ≥ 98% on real frames
   - Remove firmware temporary corrections for 29C/41% and 27C/41%
   - Restore confidence threshold from 60% back to 85%+
