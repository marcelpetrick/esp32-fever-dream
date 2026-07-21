#!/usr/bin/env python3
"""Compare automated label proposal CSVs by field."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

VALUE_FIELDS = (
    "co2_ppm",
    "hcho_raw",
    "tvoc_raw",
    "temperature_c",
    "humidity_percent",
)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", required=True, type=Path)
    parser.add_argument("--right", required=True, type=Path)
    parser.add_argument("--left-name", default="left")
    parser.add_argument("--right-name", default="right")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args(list(argv) if argv is not None else None)


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return {row["sample_id"]: row for row in reader}


def accepted(row: dict[str, str]) -> bool:
    status = row.get("proposal_status", "")
    if status:
        return status == "accepted"
    return row.get("valid", "").strip().lower() in {"1", "true", "yes", "ok"}


def parse_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def compare(left: dict[str, dict[str, str]], right: dict[str, dict[str, str]]) -> dict[str, object]:
    common_ids = sorted(set(left) & set(right))
    both_accepted = [
        sample_id
        for sample_id in common_ids
        if accepted(left[sample_id]) and accepted(right[sample_id])
    ]
    field_reports: dict[str, dict[str, object]] = {}
    for field in VALUE_FIELDS:
        exact = 0
        numeric_deltas: list[int] = []
        for sample_id in both_accepted:
            left_value = left[sample_id].get(field, "")
            right_value = right[sample_id].get(field, "")
            if left_value == right_value:
                exact += 1
            left_int = parse_int(left_value)
            right_int = parse_int(right_value)
            if left_int is not None and right_int is not None:
                numeric_deltas.append(abs(left_int - right_int))
        numeric_deltas.sort()
        total = len(both_accepted)
        field_reports[field] = {
            "exact": exact,
            "total": total,
            "exact_rate": exact / total if total else None,
            "within_1": sum(delta <= 1 for delta in numeric_deltas),
            "within_5": sum(delta <= 5 for delta in numeric_deltas),
            "within_10": sum(delta <= 10 for delta in numeric_deltas),
            "median_abs_delta": numeric_deltas[len(numeric_deltas) // 2] if numeric_deltas else None,
        }
    all_exact = sum(
        all(left[sample_id].get(field, "") == right[sample_id].get(field, "") for field in VALUE_FIELDS)
        for sample_id in both_accepted
    )
    return {
        "common_rows": len(common_ids),
        "left_rows": len(left),
        "right_rows": len(right),
        "both_accepted_rows": len(both_accepted),
        "all_fields_exact": all_exact,
        "all_fields_exact_rate": all_exact / len(both_accepted) if both_accepted else None,
        "fields": field_reports,
    }


def write_report(report: dict[str, object], output_json: Path, output_md: Path, left_name: str, right_name: str) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fields = report["fields"]
    assert isinstance(fields, dict)
    lines = [
        "# Label proposal agreement report",
        "",
        f"- Left: `{left_name}`",
        f"- Right: `{right_name}`",
        f"- Common rows: {report['common_rows']}",
        f"- Both accepted rows: {report['both_accepted_rows']}",
        f"- All fields exact: {report['all_fields_exact']}",
        "",
        "| Field | Exact | Exact rate | Within 1 | Within 5 | Within 10 | Median abs delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for field, values in fields.items():
        assert isinstance(values, dict)
        rate = values["exact_rate"]
        rate_text = "n/a" if rate is None else f"{float(rate) * 100:.2f}%"
        lines.append(
            f"| {field} | {values['exact']}/{values['total']} | {rate_text} | "
            f"{values['within_1']} | {values['within_5']} | {values['within_10']} | "
            f"{values['median_abs_delta']} |"
        )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    report = compare(read_rows(args.left), read_rows(args.right))
    write_report(report, args.output_json, args.output_md, args.left_name, args.right_name)
    print(f"[INFO] wrote {args.output_json}")
    print(f"[INFO] wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
