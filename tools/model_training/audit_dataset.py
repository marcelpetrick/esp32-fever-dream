#!/usr/bin/env python3
"""Audit whether a labeled capture dataset is sufficient for TinyML training."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

REQUIRED_DIGITS = set("0123456789")
DIGIT_RE = re.compile(r"\d")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit TinyML OCR dataset readiness.")
    parser.add_argument(
        "--labels", required=True, type=Path, help="Label CSV to audit."
    )
    parser.add_argument(
        "--json-out", required=True, type=Path, help="JSON report output."
    )
    parser.add_argument(
        "--markdown-out", required=True, type=Path, help="Markdown report output."
    )
    parser.add_argument("--min-captures", type=int, default=300)
    parser.add_argument("--min-distinct-readings", type=int, default=10)
    parser.add_argument("--min-heldout", type=int, default=50)
    parser.add_argument("--min-samples-per-digit", type=int, default=20)
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero when audit fails."
    )
    return parser.parse_args(list(argv))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader)


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "ok"}


def trusted_label(row: dict[str, str]) -> bool:
    """Reject model proposals unless a human explicitly approved them."""
    review_status = row.get("review_status", "").strip().lower()
    if review_status:
        return review_status in {"approved", "corrected", "human"}
    if "proposal_status" in row:
        return False
    return "ollama_ocr" not in row.get("notes", "").lower()


def row_label(row: dict[str, str]) -> str:
    """Build a canonical label string from whichever fields are present.

    Supports both the legacy display_text/temperature_text format and the
    current labels_environment.csv format (co2_ppm, hcho_raw, tvoc_raw,
    temperature_c, humidity_percent).  All five numeric fields contribute
    digits so the audit can count every digit position produced by
    build_digit_dataset.py.
    """
    # Legacy formats
    if row.get("display_text", "").strip():
        return row["display_text"].strip()

    # Current labels_environment.csv format
    parts: list[str] = []
    for field in ("co2_ppm", "hcho_raw", "tvoc_raw"):
        val = row.get(field, "").strip()
        if val and val != "-1":
            parts.append(f"{field}={val}")
    temp = row.get("temperature_c", "").strip()
    if temp and temp != "-1":
        parts.append(f"{temp}C")
    hum = row.get("humidity_percent", "").strip()
    if hum and hum != "-1":
        parts.append(f"{hum}%")
    if parts:
        return " ".join(parts)

    # Fallback: legacy temperature_text + humidity_percent
    return " ".join(
        part
        for part in (
            row.get("temperature_text", "").strip(),
            (
                (hum + "%")
                if hum
                else ""
            ),
        )
        if part
    )


def evaluate(
    rows: list[dict[str, str]], labels_path: Path, args: argparse.Namespace
) -> dict[str, object]:
    candidate_rows = [
        row for row in rows if truthy(row.get("valid", "true")) and row_label(row)
    ]
    untrusted_rows = [row for row in candidate_rows if not trusted_label(row)]
    valid_rows = [row for row in candidate_rows if trusted_label(row)]
    labels = [row_label(row) for row in valid_rows]
    distinct_readings = sorted(set(labels))
    split_counts = Counter(
        row.get("split", "unassigned") or "unassigned" for row in valid_rows
    )
    digit_counts = Counter()
    for label in labels:
        digit_counts.update(DIGIT_RE.findall(label))

    missing_digits = sorted(REQUIRED_DIGITS - set(digit_counts))
    underrepresented = {
        digit: digit_counts.get(digit, 0)
        for digit in sorted(REQUIRED_DIGITS)
        if digit_counts.get(digit, 0) < args.min_samples_per_digit
    }
    heldout_count = split_counts.get("validation", 0) + split_counts.get("test", 0)

    checks = {
        "minimum_captures": len(valid_rows) >= args.min_captures,
        "distinct_readings": len(distinct_readings) >= args.min_distinct_readings,
        "all_digits_present": not missing_digits,
        "samples_per_digit": not underrepresented,
        "heldout_samples": heldout_count >= args.min_heldout,
        "all_labels_trusted": not untrusted_rows,
    }
    passed = all(checks.values())

    return {
        "tool": "model_training.audit_dataset",
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "labels_csv": str(labels_path),
        "passed": passed,
        "checks": checks,
        "requirements": {
            "min_captures": args.min_captures,
            "min_distinct_readings": args.min_distinct_readings,
            "min_heldout": args.min_heldout,
            "min_samples_per_digit": args.min_samples_per_digit,
            "required_digits": "".join(sorted(REQUIRED_DIGITS)),
        },
        "summary": {
            "rows": len(rows),
            "valid_rows": len(valid_rows),
            "untrusted_rows": len(untrusted_rows),
            "distinct_readings": len(distinct_readings),
            "heldout_count": heldout_count,
            "split_counts": dict(sorted(split_counts.items())),
            "digit_counts": dict(sorted(digit_counts.items())),
            "missing_digits": missing_digits,
            "underrepresented_digits": underrepresented,
            "sample_readings": distinct_readings[:20],
        },
        "next_actions": [
            "Capture more real images only when values have changed or lighting conditions are intentionally varied.",
            "Collect readings until every digit 0-9 appears at least 20 times.",
            "Keep at least 50 validation/test frames out of tuning.",
            "Add negative examples before trusting false-accept rates.",
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    summary = report["summary"]
    requirements = report["requirements"]
    checks = report["checks"]
    assert isinstance(summary, dict)
    assert isinstance(requirements, dict)
    assert isinstance(checks, dict)

    lines = [
        "# TinyML Dataset Audit",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Labels CSV: `{report['labels_csv']}`",
        f"Status: `{'pass' if report['passed'] else 'blocked'}`",
        "",
        "## Requirements",
        "",
        f"- Minimum valid captures: {requirements['min_captures']}",
        f"- Minimum distinct readings: {requirements['min_distinct_readings']}",
        f"- Minimum held-out validation/test captures: {requirements['min_heldout']}",
        f"- Minimum samples per digit: {requirements['min_samples_per_digit']}",
        f"- Required digits: `{requirements['required_digits']}`",
        "",
        "## Checks",
        "",
    ]
    for name, passed in checks.items():
        lines.append(f"- {name}: {'pass' if passed else 'fail'}")

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Rows: {summary['rows']}",
            f"- Valid rows: {summary['valid_rows']}",
            f"- Untrusted rows excluded: {summary['untrusted_rows']}",
            f"- Distinct readings: {summary['distinct_readings']}",
            f"- Held-out rows: {summary['heldout_count']}",
            f"- Splits: `{summary['split_counts']}`",
            f"- Digit counts: `{summary['digit_counts']}`",
            f"- Missing digits: `{summary['missing_digits']}`",
            f"- Underrepresented digits: `{summary['underrepresented_digits']}`",
            f"- Sample readings: `{summary['sample_readings']}`",
            "",
            "## Next Actions",
            "",
        ]
    )
    for action in report["next_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: dict[str, object], json_path: Path, markdown_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows = read_rows(args.labels)
    report = evaluate(rows, args.labels, args)
    write_report(report, args.json_out, args.markdown_out)
    if args.strict and not report["passed"]:
        print(
            f"dataset audit blocked training; see {args.markdown_out}", file=sys.stderr
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
