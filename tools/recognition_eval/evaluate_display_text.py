#!/usr/bin/env python3
"""Evaluate labeled thermometer display text rows.

The tool intentionally depends only on the Python standard library so it can be
used early in the project before image-processing dependencies are selected.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

FULL_READING_THRESHOLD = 0.98
PER_DIGIT_THRESHOLD = 0.99
LABEL_COLUMN = "display_text"
PREDICTION_COLUMN = "predicted_display_text"
DIGIT_RE = re.compile(r"\d")


@dataclass(frozen=True)
class DisplayTextRow:
    """One labeled row from the display-text dataset CSV."""

    row_number: int
    display_text: str
    predicted_display_text: str
    sample_id: str
    split: str
    image_path: str
    failure_class: str


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate labeled thermometer display_text values from CSV.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="CSV file containing labeled display_text rows.",
    )
    parser.add_argument(
        "--json-out",
        required=True,
        type=Path,
        help="Path for the JSON evaluation report.",
    )
    parser.add_argument(
        "--markdown-out",
        required=True,
        type=Path,
        help="Path for the Markdown evaluation report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when predictions exist but acceptance thresholds are not met.",
    )
    return parser.parse_args(list(argv))


def normalize_display_text(value: str) -> str:
    """Normalize display text without changing its recognition meaning."""

    return " ".join(value.strip().split())


def read_rows(csv_path: Path) -> list[DisplayTextRow]:
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path} is empty or has no header row")
        if LABEL_COLUMN not in reader.fieldnames:
            raise ValueError(f"{csv_path} must contain a {LABEL_COLUMN!r} column")

        rows: list[DisplayTextRow] = []
        for row_number, row in enumerate(reader, start=2):
            label = normalize_display_text(row.get(LABEL_COLUMN, ""))
            if not label:
                raise ValueError(
                    f"{csv_path}:{row_number} has an empty {LABEL_COLUMN!r} value"
                )

            rows.append(
                DisplayTextRow(
                    row_number=row_number,
                    display_text=label,
                    predicted_display_text=normalize_display_text(
                        row.get(PREDICTION_COLUMN, "")
                    ),
                    sample_id=row.get("sample_id", "").strip(),
                    split=row.get("split", "").strip() or "unassigned",
                    image_path=row.get("image_path", "").strip(),
                    failure_class=row.get("failure_class", "").strip()
                    or "unclassified",
                )
            )

    return rows


def split_digits(value: str) -> list[str]:
    return DIGIT_RE.findall(value)


def score_digit_pairs(rows: list[DisplayTextRow]) -> tuple[int, int]:
    correct = 0
    compared = 0

    for row in rows:
        if not row.predicted_display_text:
            continue

        expected_digits = split_digits(row.display_text)
        actual_digits = split_digits(row.predicted_display_text)
        for expected, actual in zip(expected_digits, actual_digits):
            compared += 1
            if expected == actual:
                correct += 1

        compared += abs(len(expected_digits) - len(actual_digits))

    return correct, compared


def evaluate(rows: list[DisplayTextRow], source_csv: Path) -> dict[str, Any]:
    total_rows = len(rows)
    predicted_rows = [row for row in rows if row.predicted_display_text]
    exact_matches = sum(
        1 for row in predicted_rows if row.display_text == row.predicted_display_text
    )
    digit_correct, digit_compared = score_digit_pairs(rows)

    full_reading_accuracy = (
        exact_matches / len(predicted_rows) if predicted_rows else None
    )
    per_digit_accuracy = digit_correct / digit_compared if digit_compared else None
    predictions_available = bool(predicted_rows)

    split_counts = Counter(row.split for row in rows)
    failure_class_counts = Counter(
        row.failure_class for row in rows if row.failure_class != "unclassified"
    )

    mismatches = [
        {
            "row_number": row.row_number,
            "sample_id": row.sample_id,
            "expected": row.display_text,
            "actual": row.predicted_display_text,
            "split": row.split,
            "image_path": row.image_path,
        }
        for row in predicted_rows
        if row.display_text != row.predicted_display_text
    ]

    acceptance = {
        "full_reading_threshold": FULL_READING_THRESHOLD,
        "per_digit_threshold": PER_DIGIT_THRESHOLD,
        "invalid_or_ambiguous_rejected_explicitly": "not_evaluated",
        "full_reading_accuracy_met": (
            full_reading_accuracy >= FULL_READING_THRESHOLD
            if full_reading_accuracy is not None
            else "not_evaluated"
        ),
        "per_digit_accuracy_met": (
            per_digit_accuracy >= PER_DIGIT_THRESHOLD
            if per_digit_accuracy is not None
            else "not_evaluated"
        ),
    }

    return {
        "tool": "recognition_eval.display_text",
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "source_csv": str(source_csv),
        "status": (
            "evaluated" if predictions_available else "placeholder_no_predictions"
        ),
        "summary": {
            "total_rows": total_rows,
            "predicted_rows": len(predicted_rows),
            "unpredicted_rows": total_rows - len(predicted_rows),
            "exact_matches": exact_matches,
            "full_reading_accuracy": full_reading_accuracy,
            "digit_positions_compared": digit_compared,
            "digit_positions_correct": digit_correct,
            "per_digit_accuracy": per_digit_accuracy,
        },
        "dataset": {
            "split_counts": dict(sorted(split_counts.items())),
            "failure_class_counts": dict(sorted(failure_class_counts.items())),
        },
        "acceptance": acceptance,
        "mismatches": mismatches[:50],
        "notes": [
            "Phase 2 targets are 99% per-digit accuracy and 98% full-reading accuracy.",
            "Invalid or ambiguous image rejection is a placeholder until image-level classifications are captured.",
        ],
    }


def format_percent(value: float | None) -> str:
    if value is None:
        return "not evaluated"
    return f"{value:.2%}"


def format_acceptance(value: bool | str) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return str(value).replace("_", " ")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    acceptance = report["acceptance"]
    dataset = report["dataset"]
    lines = [
        "# Recognition Evaluation Report",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Source CSV: `{report['source_csv']}`",
        f"Status: `{report['status']}`",
        "",
        "## Summary",
        "",
        f"- Total rows: {summary['total_rows']}",
        f"- Predicted rows: {summary['predicted_rows']}",
        f"- Exact matches: {summary['exact_matches']}",
        f"- Full-reading accuracy: {format_percent(summary['full_reading_accuracy'])}",
        f"- Per-digit accuracy: {format_percent(summary['per_digit_accuracy'])}",
        "",
        "## Acceptance Placeholder",
        "",
        f"- Full-reading threshold: {acceptance['full_reading_threshold']:.2%}",
        f"- Per-digit threshold: {acceptance['per_digit_threshold']:.2%}",
        f"- Full-reading threshold met: {format_acceptance(acceptance['full_reading_accuracy_met'])}",
        f"- Per-digit threshold met: {format_acceptance(acceptance['per_digit_accuracy_met'])}",
        "- Invalid or ambiguous images rejected explicitly: "
        f"{format_acceptance(acceptance['invalid_or_ambiguous_rejected_explicitly'])}",
        "",
        "## Dataset Profile",
        "",
        "### Splits",
        "",
    ]

    for split, count in dataset["split_counts"].items():
        lines.append(f"- {split}: {count}")

    lines.extend(["", "### Failure Classes", ""])
    if dataset["failure_class_counts"]:
        for failure_class, count in dataset["failure_class_counts"].items():
            lines.append(f"- {failure_class}: {count}")
    else:
        lines.append("- none recorded")

    lines.extend(["", "## Mismatches", ""])
    if report["mismatches"]:
        lines.append("| Row | Sample | Split | Expected | Actual |")
        lines.append("| --- | --- | --- | --- | --- |")
        for mismatch in report["mismatches"]:
            lines.append(
                "| {row_number} | {sample_id} | {split} | `{expected}` | `{actual}` |".format(
                    row_number=mismatch["row_number"],
                    sample_id=mismatch["sample_id"] or "-",
                    split=mismatch["split"],
                    expected=mismatch["expected"],
                    actual=mismatch["actual"],
                )
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Notes", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def thresholds_failed(report: dict[str, Any]) -> bool:
    acceptance = report["acceptance"]
    checks = [
        acceptance["full_reading_accuracy_met"],
        acceptance["per_digit_accuracy_met"],
    ]
    return any(check is False for check in checks)


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    try:
        rows = read_rows(args.input)
        report = evaluate(rows, args.input)
        write_report(report, args.json_out, args.markdown_out)
    except OSError as error:
        print(f"recognition_eval: {error}", file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"recognition_eval: {error}", file=sys.stderr)
        return 2

    if args.strict and thresholds_failed(report):
        print("recognition_eval: acceptance thresholds were not met", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
