#!/usr/bin/env python3
"""Merge reviewed label CSVs while assigning splits by frozen capture session."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

SPLITS = ("train", "validation", "test")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", action="append", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(list(argv))


def load_policy(path: Path) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assignments: dict[str, str] = {}
    for split in SPLITS:
        for batch in document.get(split, []):
            if batch in assignments:
                raise ValueError(f"capture batch assigned more than once: {batch}")
            assignments[batch] = split
    return assignments


def apply_policy(label_paths: list[Path], policy_path: Path, output_path: Path) -> None:
    assignments = load_policy(policy_path)
    fieldnames: list[str] = []
    output_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for labels_path in label_paths:
        with labels_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError(f"{labels_path} has no header")
            for field in (*reader.fieldnames, "source_labels"):
                if field not in fieldnames:
                    fieldnames.append(field)
            for row in reader:
                batch = Path(row.get("image_path", "")).parent.name
                if batch not in assignments:
                    raise ValueError(f"capture batch has no frozen split assignment: {batch}")
                sample_id = f"{batch}_{row['sample_id']}"
                if sample_id in seen_ids:
                    raise ValueError(f"duplicate sample ID after merge: {sample_id}")
                seen_ids.add(sample_id)
                row["sample_id"] = sample_id
                row["split"] = assignments[batch]
                row["source_labels"] = str(labels_path)
                output_rows.append(row)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    temporary.replace(output_path)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    apply_policy(args.labels, args.policy, args.output)
    print(f"[INFO] wrote frozen-split labels {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
