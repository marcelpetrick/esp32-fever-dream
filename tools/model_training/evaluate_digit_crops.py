#!/usr/bin/env python3
"""Evaluate a TFLite digit classifier against digit crop labels.

This writes a compact mistake list for label/crop review.  It is deliberately
separate from training so failed models can still produce actionable debugging
artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

CLASSES = tuple("0123456789")
TARGET_SHAPE = (32, 24, 1)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digit-labels", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--splits", nargs="+", default=["validation", "test"])
    parser.add_argument("--mistakes-out", required=True, type=Path)
    parser.add_argument("--summary-out", required=True, type=Path)
    return parser.parse_args(list(argv))


def require_tensorflow():
    try:
        import tensorflow as tf  # type: ignore
    except Exception as exc:
        raise SystemExit(f"TensorFlow is required for TFLite evaluation: {exc}") from exc
    return tf


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader)


def load_crop(path: Path) -> np.ndarray:
    image = Image.open(path).convert("L").resize((24, 32))
    values = np.asarray(image, dtype=np.float32) / 255.0
    return values.reshape(TARGET_SHAPE)


def predict(interpreter, input_detail: dict, output_detail: dict, sample: np.ndarray) -> tuple[str, int]:
    scale, zero_point = input_detail["quantization"]
    if scale <= 0:
        raise ValueError("TFLite input tensor has invalid quantization scale")
    quantized = np.rint(sample / scale + zero_point)
    quantized = np.clip(quantized, -128, 127).astype(np.int8)[None, ...]
    interpreter.set_tensor(input_detail["index"], quantized)
    interpreter.invoke()
    raw = interpreter.get_tensor(output_detail["index"])[0].astype(int)
    probabilities = np.clip(raw + 128, 0, 255)
    best = int(np.argmax(probabilities))
    confidence = int((int(probabilities[best]) * 100) / 255)
    return CLASSES[best], confidence


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    tf = require_tensorflow()
    interpreter = tf.lite.Interpreter(model_path=str(args.model))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]

    selected_splits = set(args.splits)
    rows = [
        row
        for row in read_rows(args.digit_labels)
        if row.get("source") == "real" and row.get("split") in selected_splits
    ]
    mistakes: list[dict[str, object]] = []
    total = Counter()
    correct = Counter()
    confusion = Counter()
    for row in rows:
        expected = row["label"]
        predicted, confidence = predict(
            interpreter,
            input_detail,
            output_detail,
            load_crop(Path(row["image_path"])),
        )
        split = row["split"]
        total[(split, expected)] += 1
        total[(split, "ALL")] += 1
        if predicted == expected:
            correct[(split, expected)] += 1
            correct[(split, "ALL")] += 1
        else:
            confusion[(expected, predicted)] += 1
            mistakes.append(
                {
                    "split": split,
                    "sample_id": row["sample_id"],
                    "crop_path": row["image_path"],
                    "position": row.get("position", ""),
                    "expected": expected,
                    "predicted": predicted,
                    "confidence_percent": confidence,
                }
            )

    summary = {
        "model": str(args.model),
        "digit_labels": str(args.digit_labels),
        "splits": sorted(selected_splits),
        "rows": len(rows),
        "mistakes": len(mistakes),
        "accuracy": (sum(correct[(split, "ALL")] for split in selected_splits) / len(rows)) if rows else None,
        "per_split": {},
        "top_confusions": [
            {"expected": key[0], "predicted": key[1], "count": count} for key, count in confusion.most_common(25)
        ],
    }
    for split in sorted(selected_splits):
        split_total = total[(split, "ALL")]
        split_correct = correct[(split, "ALL")]
        summary["per_split"][split] = {
            "rows": split_total,
            "accuracy": (split_correct / split_total) if split_total else None,
            "per_digit": {
                digit: {
                    "rows": total[(split, digit)],
                    "accuracy": (correct[(split, digit)] / total[(split, digit)] if total[(split, digit)] else None),
                }
                for digit in CLASSES
            },
        }

    args.mistakes_out.parent.mkdir(parents=True, exist_ok=True)
    with args.mistakes_out.open("w", encoding="utf-8", newline="") as csv_file:
        fieldnames = [
            "split",
            "sample_id",
            "crop_path",
            "position",
            "expected",
            "predicted",
            "confidence_percent",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mistakes)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[INFO] accuracy={summary['accuracy']:.4f} mistakes={len(mistakes)} rows={len(rows)}")
    print(f"[INFO] wrote {args.mistakes_out}")
    print(f"[INFO] wrote {args.summary_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
