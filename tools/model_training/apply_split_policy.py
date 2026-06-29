#!/usr/bin/env python3
"""Merge reviewed label CSVs while assigning splits by frozen capture session."""

from __future__ import annotations

import argparse
import csv
import json
import re
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


def _sample_number(sample_id: str) -> int:
    match = re.search(r"(\d+)$", sample_id)
    return int(match.group(1)) if match else sys.maxsize


def load_policy(path: Path) -> tuple[dict[str, str], dict[str, list[tuple[str, float]]]]:
    """Return (batch→split, batch→[(split, fraction)]) from the policy file.

    Simple entries in "train"/"validation"/"test" lists assign the whole batch.
    Entries in "split_within" divide a batch by sorted sample number:

        "split_within": [
          {"batch": "NAME", "train": 0.8, "validation": 0.2}
        ]

    Fractions must sum to ≤ 1; any remainder is silently dropped.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    assignments: dict[str, str] = {}
    for split in SPLITS:
        for batch in document.get(split, []):
            if batch in assignments:
                raise ValueError(f"capture batch assigned more than once: {batch}")
            assignments[batch] = split

    fractions: dict[str, list[tuple[str, float]]] = {}
    for entry in document.get("split_within", []):
        batch = entry["batch"]
        if batch in assignments:
            raise ValueError(f"capture batch in both split list and split_within: {batch}")
        parts: list[tuple[str, float]] = []
        total = 0.0
        for split in SPLITS:
            frac = entry.get(split, 0.0)
            if frac > 0:
                parts.append((split, frac))
                total += frac
        if not parts:
            raise ValueError(f"split_within entry for {batch} has no fractions")
        if total > 1.001:
            raise ValueError(f"split_within fractions for {batch} sum to {total:.3f} > 1")
        fractions[batch] = parts

    return assignments, fractions


def apply_policy(label_paths: list[Path], policy_path: Path, output_path: Path) -> None:
    assignments, fractions = load_policy(policy_path)

    # Collect rows per batch for fractional batches first
    batch_rows: dict[str, list[dict[str, str]]] = {}
    fieldnames: list[str] = []
    seen_ids: set[str] = set()
    all_rows: list[dict[str, str]] = []

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
                sample_id = f"{batch}_{row['sample_id']}"
                if sample_id in seen_ids:
                    raise ValueError(f"duplicate sample ID after merge: {sample_id}")
                seen_ids.add(sample_id)
                row["sample_id"] = sample_id
                row["source_labels"] = str(labels_path)
                row["_batch"] = batch
                if batch in fractions:
                    batch_rows.setdefault(batch, []).append(row)
                elif batch in assignments:
                    row["split"] = assignments[batch]
                    all_rows.append(row)
                else:
                    raise ValueError(f"capture batch has no frozen split assignment: {batch}")

    # Apply fractional splits in sample-number order
    for batch, parts in fractions.items():
        rows = sorted(batch_rows.get(batch, []), key=lambda r: _sample_number(r["sample_id"]))
        n = len(rows)
        offset = 0
        for split, frac in parts:
            count = round(n * frac)
            for row in rows[offset: offset + count]:
                row["split"] = split
                all_rows.append(row)
            offset += count

    # Strip internal field
    for row in all_rows:
        row.pop("_batch", None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    temporary.replace(output_path)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    apply_policy(args.labels, args.policy, args.output)
    print(f"[INFO] wrote frozen-split labels {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
