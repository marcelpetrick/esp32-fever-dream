#!/usr/bin/env python3
"""Block deployment unless frozen real-model and firmware gates pass."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

MAX_MODEL_BYTES = 150 * 1024
MIN_DIGIT_ACCURACY = 0.99
MIN_CLASS_ACCURACY = 0.97
MIN_FULL_READING_ACCURACY = 0.98
MAX_FALSE_ACCEPT_RATE = 0.01
MIN_CONFIDENCE_THRESHOLD = 85


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-eval", required=True, type=Path)
    parser.add_argument("--reading-eval", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--firmware-config", required=True, type=Path)
    parser.add_argument("--recognizer-source", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(list(argv))


def evaluate_gate(
    model_eval: dict,
    reading_eval: dict,
    model_size: int,
    firmware_config: str,
    recognizer_source: str,
) -> dict[str, object]:
    test = model_eval.get("test_real_tflite")
    per_digit = test.get("per_digit", {}) if isinstance(test, dict) else {}
    class_accuracies = [
        metrics.get("accuracy")
        for metrics in per_digit.values()
        if isinstance(metrics, dict)
    ]
    threshold_match = re.search(
        r"kRecognitionMinConfidencePercent\s*=\s*(\d+)U", firmware_config
    )
    confidence_threshold = int(threshold_match.group(1)) if threshold_match else None
    full_reading_accuracy = reading_eval.get("full_reading_accuracy")
    false_accept_rate = reading_eval.get("false_accept_rate")
    checks = {
        "frozen_test_present": isinstance(test, dict),
        "test_digit_accuracy": (
            isinstance(test, dict) and float(test.get("accuracy", 0.0)) >= MIN_DIGIT_ACCURACY
        ),
        "all_digits_present_in_test": len(class_accuracies) == 10
        and all(value is not None for value in class_accuracies),
        "worst_digit_accuracy": len(class_accuracies) == 10
        and all(value is not None and float(value) >= MIN_CLASS_ACCURACY for value in class_accuracies),
        "full_reading_accuracy": full_reading_accuracy is not None
        and float(full_reading_accuracy) >= MIN_FULL_READING_ACCURACY,
        "false_accept_rate": false_accept_rate is not None
        and float(false_accept_rate) <= MAX_FALSE_ACCEPT_RATE,
        "negative_set_present": int(reading_eval.get("negative_rows", 0)) >= 50,
        "model_size": model_size <= MAX_MODEL_BYTES,
        "confidence_threshold": confidence_threshold is not None
        and confidence_threshold >= MIN_CONFIDENCE_THRESHOLD,
        "prototype_correction_removed": "Temporary mounted-prototype correction"
        not in recognizer_source,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observed": {
            "model_size_bytes": model_size,
            "confidence_threshold_percent": confidence_threshold,
            "test_digit_accuracy": test.get("accuracy") if isinstance(test, dict) else None,
            "full_reading_accuracy": reading_eval.get("full_reading_accuracy"),
            "false_accept_rate": reading_eval.get("false_accept_rate"),
            "negative_rows": reading_eval.get("negative_rows"),
        },
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = evaluate_gate(
        json.loads(args.model_eval.read_text(encoding="utf-8")),
        json.loads(args.reading_eval.read_text(encoding="utf-8")),
        args.model.stat().st_size,
        args.firmware_config.read_text(encoding="utf-8"),
        args.recognizer_source.read_text(encoding="utf-8"),
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[INFO] deployment gate {'passed' if report['passed'] else 'blocked'}: {args.json_out}")
    return 0 if report["passed"] or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
