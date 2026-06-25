# Dataset Inputs

Place local display-text label CSV files here when they are safe to keep in the
working tree.

The recognition evaluator expects a CSV header with at least:

```csv
display_text
21.7
```

Add `predicted_display_text` when a recognizer can emit decoded values for the
same samples.
