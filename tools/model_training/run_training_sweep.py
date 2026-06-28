#!/usr/bin/env python3
"""Run the fixed validation-only real-weight and seed training sweep."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_SEEDS = (173, 211, 347)
DEFAULT_REAL_WEIGHTS = (1.0, 3.0, 5.0)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digit-labels", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args(list(argv))


def qualification(report: dict[str, object]) -> tuple[bool, float]:
    validation = report["validation_real_tflite"]
    assert isinstance(validation, dict)
    per_digit = validation["per_digit"]
    assert isinstance(per_digit, dict)
    accuracies = []
    all_present = True
    for metrics in per_digit.values():
        assert isinstance(metrics, dict)
        accuracy = metrics["accuracy"]
        if accuracy is None:
            all_present = False
        else:
            accuracies.append(float(accuracy))
    worst = min(accuracies, default=0.0)
    overall = float(validation["accuracy"])
    return all_present and overall >= 0.99 and worst >= 0.97, worst


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    script = Path(__file__).with_name("train_digit_classifier.py")
    results: list[dict[str, object]] = []
    for real_weight in DEFAULT_REAL_WEIGHTS:
        for seed in DEFAULT_SEEDS:
            candidate_dir = args.output_dir / f"real_weight_{real_weight:g}" / f"seed_{seed}"
            command = [
                args.python,
                str(script),
                "--digit-labels",
                str(args.digit_labels),
                "--output-dir",
                str(candidate_dir),
                "--epochs",
                str(args.epochs),
                "--seed",
                str(seed),
                "--real-weight",
                str(real_weight),
            ]
            subprocess.run(command, check=True)
            report_path = candidate_dir / "digit_classifier_eval.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            qualified, worst_digit = qualification(report)
            validation = report["validation_real_tflite"]
            results.append(
                {
                    "real_weight": real_weight,
                    "seed": seed,
                    "validation_accuracy": validation["accuracy"],
                    "worst_digit_accuracy": worst_digit,
                    "validation_qualified": qualified,
                    "report": str(report_path),
                    "model": report["tflite_model"],
                }
            )
    ranked = sorted(
        results,
        key=lambda result: (
            bool(result["validation_qualified"]),
            float(result["worst_digit_accuracy"]),
            float(result["validation_accuracy"]),
        ),
        reverse=True,
    )
    summary = {
        "digit_labels": str(args.digit_labels),
        "test_evaluated": False,
        "selection_metric": "validation qualification, worst digit, overall accuracy",
        "candidates": ranked,
        "best_candidate": ranked[0] if ranked else None,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "training_sweep_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[INFO] wrote {summary_path}")
    return 0 if ranked and bool(ranked[0]["validation_qualified"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
