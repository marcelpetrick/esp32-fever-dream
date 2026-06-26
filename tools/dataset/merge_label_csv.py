#!/usr/bin/env python3
"""Merge multiple label CSV files into one training/audit CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge fixed-display label CSV files.")
    parser.add_argument("--labels", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    fieldnames: list[str] = []
    rows: list[dict[str, str]] = []
    for path in args.labels:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError(f"{path} has no header")
            for fieldname in reader.fieldnames:
                if fieldname not in fieldnames:
                    fieldnames.append(fieldname)
            if "source_labels" not in fieldnames:
                fieldnames.append("source_labels")
            for row in reader:
                row["sample_id"] = f"{path.parent.name}_{row['sample_id']}"
                row["source_labels"] = str(path)
                rows.append(row)

    if not fieldnames:
        raise ValueError("no labels provided")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[INFO] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
