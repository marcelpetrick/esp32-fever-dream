#!/usr/bin/env python3
"""Create per-position contact sheets for human digit-crop verification."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digit-labels", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-per-position", type=int, default=100)
    return parser.parse_args(list(argv))


def create_sheets(labels_path: Path, output_dir: Path, maximum: int) -> dict[str, int]:
    if maximum < 1:
        raise ValueError("maximum must be positive")
    with labels_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = [row for row in csv.DictReader(csv_file) if row.get("source") == "real"]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["position"]].append(row)
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for position, position_rows in sorted(grouped.items()):
        selected = position_rows[:maximum]
        columns = 10
        cell_width = 96
        cell_height = 72
        row_count = (len(selected) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_width, row_count * cell_height), "white")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(selected):
            crop = Image.open(row["image_path"]).convert("L").resize((48, 64), Image.Resampling.NEAREST)
            x = (index % columns) * cell_width
            y = (index // columns) * cell_height
            sheet.paste(crop.convert("RGB"), (x, y))
            draw.text((x + 52, y + 4), f"label={row['label']}", fill="black")
            draw.text((x + 52, y + 20), row["split"][:5], fill="black")
        path = output_dir / f"{position}.png"
        sheet.save(path)
        counts[position] = len(selected)
    (output_dir / "crop_review_sheets.json").write_text(
        json.dumps({"source": str(labels_path), "counts": counts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return counts


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    counts = create_sheets(args.digit_labels, args.output_dir, args.max_per_position)
    print(f"[INFO] wrote {len(counts)} crop review sheets to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
