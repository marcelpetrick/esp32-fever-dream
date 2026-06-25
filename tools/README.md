# Local Tooling

This directory contains stdlib-only Python tooling for dataset and recognition
evaluation work.

## Recognition Evaluation

Run the display-text evaluator against a CSV with at least a `display_text`
column:

```sh
python3 tools/recognition_eval/evaluate_display_text.py \
    --input tools/dataset/display_text_labels.csv \
    --json-out build/recognition_eval.json \
    --markdown-out build/recognition_eval.md
```

Optional CSV columns:

- `sample_id`: stable sample identifier.
- `split`: dataset split such as `train`, `validation`, or `test`.
- `image_path`: source image path for traceability.
- `predicted_display_text`: decoded text to compare with `display_text`.
- `failure_class`: known failure class for rejected or ambiguous samples.

If `predicted_display_text` is absent or empty for every row, the tool writes a
dataset profile and a placeholder evaluation status. Once predictions are
available, it reports full-reading accuracy and per-digit accuracy against the
current Phase 2 thresholds.
