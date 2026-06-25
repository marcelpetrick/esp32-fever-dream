#!/usr/bin/env python3
"""Build real and synthetic fixed-display digit crops for TinyML training."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

CLASSES = tuple("0123456789")
TARGET_SIZE = (24, 32)

TEMP_DIGIT_BOXES = {
    0: (395, 315, 422, 350),
    1: (421, 315, 448, 350),
}
HUMIDITY_DIGIT_BOXES = {
    0: (525, 314, 552, 349),
    1: (550, 314, 577, 349),
}

FONT_CANDIDATES = (
    "/usr/share/fonts/adobe-source-sans/SourceSans3-Black.otf",
    "/usr/share/fonts/adobe-source-sans/SourceSansPro-Black.otf",
    "/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
)


@dataclass(frozen=True)
class CropRow:
    sample_id: str
    image_path: Path
    label: str
    source: str
    split: str
    origin: str
    position: str


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create digit-crop train/validation/test data from fixed display labels.",
    )
    parser.add_argument("--labels", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--synthetic-per-digit", type=int, default=250)
    parser.add_argument("--seed", type=int, default=173)
    parser.add_argument("--real-test-every", type=int, default=10)
    parser.add_argument("--real-validation-every", type=int, default=5)
    return parser.parse_args(list(argv))


def read_label_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError(f"{path} has no header")
            for row in reader:
                row["_labels_path"] = str(path)
                rows.append(row)
    return rows


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "ok"}


def split_for_index(index: int, test_every: int, validation_every: int) -> str:
    if test_every > 0 and index % test_every == 0:
        return "test"
    if validation_every > 0 and index % validation_every == 0:
        return "validation"
    return "train"


def normalize_crop(crop: Image.Image) -> Image.Image:
    gray = crop.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    return gray.resize(TARGET_SIZE, Image.Resampling.BILINEAR)


def save_real_crops(
    rows: list[dict[str, str]], output_dir: Path, args: argparse.Namespace
) -> list[CropRow]:
    crop_rows: list[CropRow] = []
    crops_dir = output_dir / "crops"
    for row_index, row in enumerate(rows, start=1):
        if not truthy(row.get("valid", "true")):
            continue
        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = Path.cwd() / image_path
        if not image_path.exists():
            continue

        temperature = f"{float(row['temperature_c']):.0f}".zfill(2)[-2:]
        humidity = f"{int(row['humidity_percent']):02d}"[-2:]
        split = row.get("split") or split_for_index(
            row_index, args.real_test_every, args.real_validation_every
        )
        image = Image.open(image_path).convert("RGB")
        for prefix, text, boxes in (
            ("temp", temperature, TEMP_DIGIT_BOXES),
            ("humidity", humidity, HUMIDITY_DIGIT_BOXES),
        ):
            for position, digit in enumerate(text):
                crop = normalize_crop(image.crop(boxes[position]))
                batch_id = image_path.parent.name
                sample_id = f"real_{batch_id}_{row['sample_id']}_{prefix}_{position}_{digit}"
                output_path = crops_dir / split / digit / f"{sample_id}.png"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                crop.save(output_path)
                crop_rows.append(
                    CropRow(
                        sample_id=sample_id,
                        image_path=output_path,
                        label=digit,
                        source="real",
                        split=split,
                        origin=row.get("_labels_path", ""),
                        position=f"{prefix}_{position}",
                    )
                )
    return crop_rows


def load_fonts() -> list[ImageFont.FreeTypeFont]:
    fonts: list[ImageFont.FreeTypeFont] = []
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            for size in (31, 33, 35, 37):
                fonts.append(ImageFont.truetype(str(path), size=size))
    if not fonts:
        raise RuntimeError("no usable system font found for synthetic digit generation")
    return fonts


def render_synthetic_digit(digit: str, rng: random.Random, fonts: list[ImageFont.FreeTypeFont]) -> Image.Image:
    canvas = Image.new("L", (44, 52), rng.randint(0, 10))
    draw = ImageDraw.Draw(canvas)
    font = rng.choice(fonts)
    bbox = draw.textbbox((0, 0), digit, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = (canvas.width - width) // 2 + rng.randint(-3, 3)
    y = (canvas.height - height) // 2 + rng.randint(-4, 3)
    intensity = rng.randint(178, 245)
    draw.text((x, y), digit, fill=intensity, font=font)

    if rng.random() < 0.85:
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.15, 1.05)))
    if rng.random() < 0.35:
        canvas = ImageOps.autocontrast(canvas, cutoff=rng.randint(0, 4))

    arr = np.asarray(canvas, dtype=np.int16)
    arr = np.clip(arr + rng.normalvariate(0.0, 1.0), 0, 255)
    noise = rng.randint(0, 9)
    if noise:
        arr = np.clip(arr + np.random.default_rng(rng.randrange(1 << 30)).normal(0, noise, arr.shape), 0, 255)
    canvas = Image.fromarray(arr.astype(np.uint8), mode="L")
    return normalize_crop(canvas)


def synthetic_split(index: int) -> str:
    if index % 10 == 0:
        return "test"
    if index % 5 == 0:
        return "validation"
    return "train"


def save_synthetic_crops(output_dir: Path, count_per_digit: int, seed: int) -> list[CropRow]:
    rng = random.Random(seed)
    fonts = load_fonts()
    crop_rows: list[CropRow] = []
    crops_dir = output_dir / "crops"
    for digit in CLASSES:
        for index in range(1, count_per_digit + 1):
            split = synthetic_split(index)
            crop = render_synthetic_digit(digit, rng, fonts)
            sample_id = f"synthetic_{digit}_{index:04d}"
            output_path = crops_dir / split / digit / f"{sample_id}.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            crop.save(output_path)
            crop_rows.append(
                CropRow(
                    sample_id=sample_id,
                    image_path=output_path,
                    label=digit,
                    source="synthetic",
                    split=split,
                    origin="font_rendered_display_style",
                    position="synthetic_digit",
                )
            )
    return crop_rows


def write_manifest(rows: list[CropRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "sample_id",
                "image_path",
                "label",
                "source",
                "split",
                "origin",
                "position",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sample_id": row.sample_id,
                    "image_path": row.image_path,
                    "label": row.label,
                    "source": row.source,
                    "split": row.split,
                    "origin": row.origin,
                    "position": row.position,
                }
            )


def write_report(rows: list[CropRow], output_path: Path) -> None:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        key = f"{row.source}_{row.split}"
        counts.setdefault(key, {})
        counts[key][row.label] = counts[key].get(row.label, 0) + 1

    report = {
        "tool": "model_training.build_digit_dataset",
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "target_size": TARGET_SIZE,
        "classes": CLASSES,
        "rows": len(rows),
        "counts": counts,
        "limitations": [
            "Only digits 2, 3, 4, and 9 are present in real captures so far.",
            "Synthetic crops are for prototype training only and are not final validation evidence.",
        ],
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_label_rows(args.labels)
    crop_rows = save_real_crops(rows, output_dir, args)
    crop_rows.extend(save_synthetic_crops(output_dir, args.synthetic_per_digit, args.seed))
    write_manifest(crop_rows, output_dir / "digit_labels.csv")
    write_report(crop_rows, output_dir / "digit_dataset_report.json")
    print(f"[INFO] wrote {output_dir / 'digit_labels.csv'}")
    print(f"[INFO] wrote {output_dir / 'digit_dataset_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
