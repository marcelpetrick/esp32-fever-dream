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
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.model_training.build_digit_dataset import (  # noqa: E402
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
    normalize_crop,
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
    should_accept: bool | None


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
        "--confidence-threshold",
        type=int,
        default=85,
        help="Minimum per-reading digit confidence for acceptance (default: 85).",
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
                is_valid = truthy(row.get("valid", "true"))
                image_path = Path(row["image_path"])
                if not image_path.is_absolute():
                    image_path = Path.cwd() / image_path
                cases.append(
                    ImageCase(
                        image_path=image_path,
                        expected_temperature=(
                            f"{float(row['temperature_c']):.0f}".zfill(2)[-2:]
                            if is_valid
                            else None
                        ),
                        expected_humidity=(
                            f"{int(row['humidity_percent']):02d}"[-2:] if is_valid else None
                        ),
                        expected_co2=optional_four_digit(row, "co2_ppm") if is_valid else None,
                        expected_hcho=optional_four_digit(row, "hcho_raw") if is_valid else None,
                        expected_tvoc=optional_four_digit(row, "tvoc_raw") if is_valid else None,
                        sample_id=row.get("sample_id") or image_path.stem,
                        should_accept=is_valid,
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
                    should_accept=None,
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
) -> np.ndarray:
    raw_crop = crop_digit(image, bounds, relative_box, fallback_box)
    crop = normalize_crop(raw_crop)
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


def rejected_result(case: ImageCase, reason: str) -> dict:
    return {
        "sample_id": case.sample_id,
        "image_path": str(case.image_path),
        "predicted_co2_ppm": "",
        "predicted_hcho_raw": "",
        "predicted_tvoc_raw": "",
        "predicted_temperature_c": "",
        "predicted_humidity_percent": "",
        "predicted_digits": "",
        "min_confidence_percent": 0,
        "digit_confidences_percent": "",
        "group_min_confidences_percent": "",
        "expected_co2_ppm": case.expected_co2 or "",
        "expected_hcho_raw": case.expected_hcho or "",
        "expected_tvoc_raw": case.expected_tvoc or "",
        "expected_temperature_c": case.expected_temperature or "",
        "expected_humidity_percent": case.expected_humidity or "",
        "field_match": "",
        "accepted": "false",
        "rejection_reason": reason,
        "should_accept": (
            "true" if case.should_accept is True else "false" if case.should_accept is False else ""
        ),
        "match": "false" if case.should_accept is True else "",
    }


def run_case(
    case: ImageCase,
    interpreter,
    input_detail: dict,
    output_detail: dict,
    confidence_threshold: int,
) -> dict:
    image = Image.open(case.image_path).convert("RGB")
    bounds = locate_display(image)
    if bounds is None:
        return rejected_result(case, "display_not_found")
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
                crop_to_input(image, bounds, relative_box, fallback_box),
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
    min_confidence = min(all_confidences)
    accepted = min_confidence >= confidence_threshold
    is_match = (
        accepted
        and bool(comparable)
        and all(predicted[key] == value for key, value in comparable.items())
    )
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
        "min_confidence_percent": min_confidence,
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
        "accepted": "true" if accepted else "false",
        "rejection_reason": "" if accepted else "confidence_below_threshold",
        "should_accept": (
            "true" if case.should_accept is True else "false" if case.should_accept is False else ""
        ),
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
        "accepted",
        "rejection_reason",
        "should_accept",
        "match",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict], output_path: Path, model_path: Path) -> dict:
    positives = [row for row in rows if row["should_accept"] == "true"]
    negatives = [row for row in rows if row["should_accept"] == "false"]
    matches = [row for row in positives if row["match"] == "true"]
    accepted_positives = [row for row in positives if row["accepted"] == "true"]
    false_accepts = [row for row in negatives if row["accepted"] == "true"]
    field_names = (
        ("co2", "predicted_co2_ppm", "expected_co2_ppm"),
        ("hcho", "predicted_hcho_raw", "expected_hcho_raw"),
        ("tvoc", "predicted_tvoc_raw", "expected_tvoc_raw"),
        ("temperature", "predicted_temperature_c", "expected_temperature_c"),
        ("humidity", "predicted_humidity_percent", "expected_humidity_percent"),
    )
    raw_field_accuracy = {}
    accepted_field_accuracy = {}
    digit_correct = 0
    digit_total = 0
    for name, predicted, expected in field_names:
        comparable = [row for row in positives if row[expected]]
        raw_correct = sum(row[predicted] == row[expected] for row in comparable)
        accepted_correct = sum(
            row["accepted"] == "true" and row[predicted] == row[expected]
            for row in comparable
        )
        raw_field_accuracy[name] = {
            "correct": raw_correct,
            "total": len(comparable),
            "accuracy": raw_correct / len(comparable) if comparable else None,
        }
        accepted_field_accuracy[name] = {
            "correct": accepted_correct,
            "total": len(comparable),
            "accuracy": accepted_correct / len(comparable) if comparable else None,
        }
        for row in comparable:
            predicted_text = row[predicted]
            for index, truth in enumerate(row[expected]):
                digit_total += 1
                digit_correct += index < len(predicted_text) and predicted_text[index] == truth
    summary = {
        "model": str(model_path),
        "rows": len(rows),
        "positive_rows": len(positives),
        "negative_rows": len(negatives),
        "accepted_positive_rows": len(accepted_positives),
        "exact_matches": len(matches),
        "full_reading_accuracy": (len(matches) / len(positives)) if positives else None,
        "digit_accuracy": digit_correct / digit_total if digit_total else None,
        "raw_field_accuracy": raw_field_accuracy,
        "accepted_field_accuracy": accepted_field_accuracy,
        "false_accepts": len(false_accepts),
        "false_accept_rate": len(false_accepts) / len(negatives) if negatives else None,
        "positive_rejection_rate": (
            (len(positives) - len(accepted_positives)) / len(positives)
            if positives
            else None
        ),
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
    if not 0 <= args.confidence_threshold <= 100:
        raise ValueError("--confidence-threshold must be between 0 and 100")
    rows = [
        run_case(case, interpreter, input_detail, output_detail, args.confidence_threshold)
        for case in cases
    ]
    write_csv(rows, args.output)
    summary = write_summary(rows, args.summary_json, args.model)

    accuracy = summary["full_reading_accuracy"]
    accuracy_text = "n/a" if accuracy is None else f"{accuracy:.4f}"
    print(
        f"[INFO] rows={summary['rows']} positives={summary['positive_rows']} "
        f"full_reading_accuracy={accuracy_text}"
    )
    print(f"[INFO] min_confidence={summary['min_confidence_percent']} avg_min_confidence={summary['average_min_confidence_percent']}")
    print(f"[INFO] wrote {args.output}")
    print(f"[INFO] wrote {args.summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
