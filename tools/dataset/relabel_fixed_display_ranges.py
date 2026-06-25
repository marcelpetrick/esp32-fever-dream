#!/usr/bin/env python3
"""Apply per-sample display labels to a fixed-layout capture label CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch fixed-display labels by sample range.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--range",
        action="append",
        default=[],
        metavar="START-END:TEMP_C:HUMIDITY",
        help="Inclusive capture index range, for example 1-15:29:49.",
    )
    parser.add_argument(
        "--invalid",
        action="append",
        default=[],
        metavar="INDEX",
        help="Capture index to mark invalid.",
    )
    return parser.parse_args(list(argv))


def parse_ranges(values: list[str]) -> list[tuple[int, int, float, int]]:
    parsed: list[tuple[int, int, float, int]] = []
    for value in values:
        range_part, temp_part, humidity_part = value.split(":", maxsplit=2)
        start_part, end_part = range_part.split("-", maxsplit=1)
        parsed.append((int(start_part), int(end_part), float(temp_part), int(humidity_part)))
    return parsed


def sample_index(sample_id: str) -> int:
    return int(sample_id.rsplit("_", maxsplit=1)[1])


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    ranges = parse_ranges(args.range)
    invalid = {int(value) for value in args.invalid}

    with args.input.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{args.input} has no header")
        rows = list(reader)
        fieldnames = reader.fieldnames

    for row in rows:
        index = sample_index(row["sample_id"])
        for start, end, temperature_c, humidity_percent in ranges:
            if start <= index <= end:
                temp_text = f"{temperature_c:g}C"
                row["temperature_text"] = temp_text
                row["temperature_c"] = f"{temperature_c:.2f}"
                row["humidity_percent"] = str(humidity_percent)
                row["display_text"] = f"{temp_text} {humidity_percent}%"
                row["predicted_display_text"] = row["display_text"]
                row["notes"] = (row.get("notes", "") + ";range_relabelled").strip(";")
        if index in invalid:
            row["valid"] = "false"
            row["notes"] = (row.get("notes", "") + ";invalid_visual_contact_sheet").strip(";")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[INFO] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
