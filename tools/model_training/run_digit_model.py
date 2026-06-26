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

from build_digit_dataset import (
    CO2_DIGIT_BOXES,
    HCHO_DIGIT_BOXES,
    HUMIDITY_DIGIT_BOXES,
    RELATIVE_CO2_DIGIT_BOXES,
    RELATIVE_HCHO_DIGIT_BOXES,
    RELATIVE_HUMIDITY_DIGIT_BOXES,
    RELATIVE_TVOC_DIGIT_BOXES,
    TARGET_SIZE,
    TEMP_DIGIT_BOXES,
    TVOC_DIGIT_BOXES,
    crop_digit,
    locate_display,
    relative_temp_boxes,
)


@dataclass(frozen=True)
class ImageCase:
    image_path: Path
    expected_temperature: str | None
    expected_humidity: str | None
    expected_co2: str | None
    expected_hcho: str | None
    expected_tvoc: str | None
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


def optional_four_digit(row: dict[str, str], field: str) -> str | None:
    value = row.get(field, "").strip()
    if not value:
        return None
    return f"{int(value):04d}"[-4:]


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
                        expected_co2=optional_four_digit(row, "co2_ppm"),
                        expected_hcho=optional_four_digit(row, "hcho_raw"),
                        expected_tvoc=optional_four_digit(row, "tvoc_raw"),
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
                    expected_co2=None,
                    expected_hcho=None,
                    expected_tvoc=None,
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


def crop_to_input(
    image: Image.Image,
    bounds,
    relative_box: tuple[int, int, int, int],
    fallback_box: tuple[int, int, int, int],
    resample: Image.Resampling,
) -> np.ndarray:
    crop = ImageOps.grayscale(crop_digit(image, bounds, relative_box, fallback_box))
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
    bounds = locate_display(image)
    temp_boxes = relative_temp_boxes(bounds)
    digit_groups = [
        ("co2", [RELATIVE_CO2_DIGIT_BOXES[index] for index in range(4)], [CO2_DIGIT_BOXES[index] for index in range(4)]),
        ("hcho", [RELATIVE_HCHO_DIGIT_BOXES[index] for index in range(4)], [HCHO_DIGIT_BOXES[index] for index in range(4)]),
        ("tvoc", [RELATIVE_TVOC_DIGIT_BOXES[index] for index in range(4)], [TVOC_DIGIT_BOXES[index] for index in range(4)]),
        ("temperature", [temp_boxes[0], temp_boxes[1]], [TEMP_DIGIT_BOXES[0], TEMP_DIGIT_BOXES[1]]),
        (
            "humidity",
            [RELATIVE_HUMIDITY_DIGIT_BOXES[0], RELATIVE_HUMIDITY_DIGIT_BOXES[1]],
            [HUMIDITY_DIGIT_BOXES[0], HUMIDITY_DIGIT_BOXES[1]],
        ),
    ]
    predicted: dict[str, str] = {}
    group_confidences: dict[str, list[int]] = {}
    all_digits: list[str] = []
    all_confidences: list[int] = []
    for group_name, relative_boxes, fallback_boxes in digit_groups:
        group_digits: list[str] = []
        group_values: list[int] = []
        for relative_box, fallback_box in zip(relative_boxes, fallback_boxes, strict=True):
            digit, confidence, _ = predict_digit(
                interpreter,
                input_detail,
                output_detail,
                crop_to_input(image, bounds, relative_box, fallback_box, resample),
            )
            group_digits.append(digit)
            group_values.append(confidence)
        predicted[group_name] = "".join(group_digits)
        group_confidences[group_name] = group_values
        all_digits.extend(group_digits)
        all_confidences.extend(group_values)

    expected = {
        "co2": case.expected_co2,
        "hcho": case.expected_hcho,
        "tvoc": case.expected_tvoc,
        "temperature": case.expected_temperature,
        "humidity": case.expected_humidity,
    }
    comparable = {key: value for key, value in expected.items() if value is not None}
    is_match = bool(comparable) and all(predicted[key] == value for key, value in comparable.items())
    field_match = {
        key: ("true" if expected_value is not None and predicted[key] == expected_value else "false")
        for key, expected_value in expected.items()
        if expected_value is not None
    }
    return {
        "sample_id": case.sample_id,
        "image_path": str(case.image_path),
        "predicted_co2_ppm": predicted["co2"],
        "predicted_hcho_raw": predicted["hcho"],
        "predicted_tvoc_raw": predicted["tvoc"],
        "predicted_temperature_c": predicted["temperature"],
        "predicted_humidity_percent": predicted["humidity"],
        "predicted_digits": "".join(all_digits),
        "min_confidence_percent": min(all_confidences),
        "digit_confidences_percent": "/".join(str(value) for value in all_confidences),
        "group_min_confidences_percent": ";".join(
            f"{group_name}:{min(values)}" for group_name, values in group_confidences.items()
        ),
        "expected_co2_ppm": case.expected_co2 or "",
        "expected_hcho_raw": case.expected_hcho or "",
        "expected_tvoc_raw": case.expected_tvoc or "",
        "expected_temperature_c": case.expected_temperature or "",
        "expected_humidity_percent": case.expected_humidity or "",
        "field_match": ";".join(f"{key}:{value}" for key, value in field_match.items()),
        "match": "true" if is_match else "false" if comparable else "",
    }


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "image_path",
        "predicted_co2_ppm",
        "predicted_hcho_raw",
        "predicted_tvoc_raw",
        "predicted_temperature_c",
        "predicted_humidity_percent",
        "predicted_digits",
        "min_confidence_percent",
        "digit_confidences_percent",
        "group_min_confidences_percent",
        "expected_co2_ppm",
        "expected_hcho_raw",
        "expected_tvoc_raw",
        "expected_temperature_c",
        "expected_humidity_percent",
        "field_match",
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
