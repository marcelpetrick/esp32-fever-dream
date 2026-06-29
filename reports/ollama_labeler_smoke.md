# Ollama Labeler Remediation Smoke Test

Run UTC: 2026-06-29 05:31.

Command:

```sh
python3 tools/dataset/ollama_label_batch.py \
  --dataset-dir tools/dataset/captures/serial_timed_fast_20260627T1205Z \
  --model qwen3-vl:4b --num-ctx 2048 --num-predict 96 \
  --request-timeout 30 --total-timeout 30 --retries 1 \
  --shuffle --seed 347 --limit 20
```

Results:

- Frames completed: 20/20.
- Accepted proposals: 18.
- Model-rejected proposals: 2.
- Errors/timeouts: 0.
- Slowest request: 2.8 seconds.
- Duplicate sample IDs: 0 (atomic keyed rewrite).
- Resume retained prior accepted rows and retried prior errors.
- Structured Qwen output arrived through Ollama's `thinking` stream field; the
  client now supports that behavior without enabling automatic trust.

This passes the labeler reliability smoke gate. It does not validate label
accuracy: every result remains an untrusted proposal pending human review.
