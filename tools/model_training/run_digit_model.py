#!/usr/bin/env python3
"""Run the fixed-display TFLite digit model against full-frame images."""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageOps

from build_digit_dataset import HUMIDITY_DIGIT_BOXES, TARGET_SIZE, TEMP_DIGIT_BOXES


@dataclass(frozen=True)
class ImageCase:
    image_path: Path
    expected_temperature: str | None
    expected_humidity: str | None
    sample_id: str


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the generated TFLite digit model against one or more fixed-display images.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models/generated/digit_classifier_int8.tflite"),
        help="Path to the int8 TFLite digit classifier.",
    )
    parser.add_argument(
        "--labels",
        action="append",
        type=Path,
        help="Label CSV with image_path, temperature_c, humidity_percent columns. Can be repeated.",
    )
    parser.add_argument(
        "--images",
        action="append",
        default=[],
        help="Image path or shell glob. Use this for unlabeled ad-hoc inference.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/generated/digit_model_predictions.csv"),
        help="CSV output path.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path("models/generated/digit_model_predictions_summary.json"),
        help="JSON summary output path.",
    )
    parser.add_argument(
        "--resample",
        choices=["nearest", "bilinear"],
        default="nearest",
        help="Resize mode for digit crops. nearest matches current firmware preprocessing.",
    )
    return parser.parse_args(list(argv))


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "ok"}


def read_label_cases(paths: list[Path]) -> list[ImageCase]:
    cases: list[ImageCase] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError(f"{path} has no header")
            for row in reader:
                if not truthy(row.get("valid", "true")):
                    continue
                image_path = Path(row["image_path"])
                if not image_path.is_absolute():
                    image_path = Path.cwd() / image_path
                cases.append(
                    ImageCase(
                        image_path=image_path,
                        expected_temperature=f"{float(row['temperature_c']):.0f}".zfill(2)[-2:],
                        expected_humidity=f"{int(row['humidity_percent']):02d}"[-2:],
                        sample_id=row.get("sample_id") or image_path.stem,
                    )
                )
    return cases


def read_image_cases(patterns: list[str]) -> list[ImageCase]:
    cases: list[ImageCase] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if not matches:
            matches = [pattern]
        for match in matches:
            image_path = Path(match)
            if not image_path.is_absolute():
                image_path = Path.cwd() / image_path
            cases.append(
                ImageCase(
                    image_path=image_path,
                    expected_temperature=None,
                    expected_humidity=None,
                    sample_id=image_path.stem,
                )
            )
    return cases


def require_tensorflow():
    try:
        import tensorflow as tf  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "TensorFlow is required for the TFLite interpreter. Run `./scripts/setup_ml_env.sh` "
            f"or use `.venv-ml/bin/python`. Import failed: {exc}"
        ) from exc
    return tf


def crop_to_input(image: Image.Image, box: tuple[int, int, int, int], resample: Image.Resampling) -> np.ndarray:
    crop = ImageOps.grayscale(image.crop(box))
    crop = ImageOps.autocontrast(crop, cutoff=1)
    crop = crop.resize(TARGET_SIZE, resample)
    values = np.asarray(crop, dtype=np.int16) - 128
    return values.astype(np.int8).reshape(1, TARGET_SIZE[1], TARGET_SIZE[0], 1)


def predict_digit(interpreter, input_detail: dict, output_detail: dict, tensor: np.ndarray) -> tuple[str, int, list[int]]:
    interpreter.set_tensor(input_detail["index"], tensor)
    interpreter.invoke()
    raw = interpreter.get_tensor(output_detail["index"])[0].astype(int)
    probabilities = np.clip(raw + 128, 0, 255)
    best = int(np.argmax(probabilities))
    confidences = [int((int(value) * 100) / 255) for value in probabilities]
    return str(best), confidences[best], confidences


def run_case(case: ImageCase, interpreter, input_detail: dict, output_detail: dict, resample: Image.Resampling) -> dict:
    image = Image.open(case.image_path).convert("RGB")
    boxes = [
        TEMP_DIGIT_BOXES[0],
        TEMP_DIGIT_BOXES[1],
        HUMIDITY_DIGIT_BOXES[0],
        HUMIDITY_DIGIT_BOXES[1],
    ]
    digits: list[str] = []
    confidences: list[int] = []
    for box in boxes:
        digit, confidence, _ = predict_digit(
            interpreter,
            input_detail,
            output_detail,
            crop_to_input(image, box, resample),
        )
        digits.append(digit)
        confidences.append(confidence)

    predicted_temperature = "".join(digits[:2])
    predicted_humidity = "".join(digits[2:])
    expected_temperature = case.expected_temperature
    expected_humidity = case.expected_humidity
    is_match = (
        expected_temperature is not None
        and expected_humidity is not None
        and predicted_temperature == expected_temperature
        and predicted_humidity == expected_humidity
    )
    return {
        "sample_id": case.sample_id,
        "image_path": str(case.image_path),
        "predicted_temperature_c": predicted_temperature,
        "predicted_humidity_percent": predicted_humidity,
        "predicted_digits": "".join(digits),
        "min_confidence_percent": min(confidences),
        "digit_confidences_percent": "/".join(str(value) for value in confidences),
        "expected_temperature_c": expected_temperature or "",
        "expected_humidity_percent": expected_humidity or "",
        "match": "true" if is_match else "false" if expected_temperature is not None else "",
    }


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "image_path",
        "predicted_temperature_c",
        "predicted_humidity_percent",
        "predicted_digits",
        "min_confidence_percent",
        "digit_confidences_percent",
        "expected_temperature_c",
        "expected_humidity_percent",
        "match",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict], output_path: Path, model_path: Path) -> dict:
    labeled = [row for row in rows if row["match"]]
    matches = [row for row in labeled if row["match"] == "true"]
    summary = {
        "model": str(model_path),
        "rows": len(rows),
        "labeled_rows": len(labeled),
        "exact_matches": len(matches),
        "exact_accuracy": (len(matches) / len(labeled)) if labeled else None,
        "min_confidence_percent": min((int(row["min_confidence_percent"]) for row in rows), default=None),
        "average_min_confidence_percent": (
            sum(int(row["min_confidence_percent"]) for row in rows) / len(rows) if rows else None
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.labels and not args.images:
        raise SystemExit("Provide at least one --labels CSV or --images glob.")
    if not args.model.exists():
        raise SystemExit(f"model not found: {args.model}")

    cases = read_label_cases(args.labels or []) + read_image_cases(args.images)
    cases = [case for case in cases if case.image_path.exists()]
    if not cases:
        raise SystemExit("no input images found")

    tf = require_tensorflow()
    interpreter = tf.lite.Interpreter(model_path=str(args.model))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    resample = Image.Resampling.NEAREST if args.resample == "nearest" else Image.Resampling.BILINEAR

    rows = [run_case(case, interpreter, input_detail, output_detail, resample) for case in cases]
    write_csv(rows, args.output)
    summary = write_summary(rows, args.summary_json, args.model)

    accuracy = summary["exact_accuracy"]
    accuracy_text = "n/a" if accuracy is None else f"{accuracy:.4f}"
    print(f"[INFO] rows={summary['rows']} labeled={summary['labeled_rows']} exact_accuracy={accuracy_text}")
    print(f"[INFO] min_confidence={summary['min_confidence_percent']} avg_min_confidence={summary['average_min_confidence_percent']}")
    print(f"[INFO] wrote {args.output}")
    print(f"[INFO] wrote {args.summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
