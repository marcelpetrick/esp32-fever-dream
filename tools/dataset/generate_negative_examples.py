#!/usr/bin/env python3
"""Generate negative/ambiguous OCR examples from existing labeled images."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import random
import sys
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[2]

LABEL_FIELDS = [
    "sample_id",
    "image_path",
    "temperature_c",
    "humidity_percent",
    "co2_ppm",
    "hcho_raw",
    "tvoc_raw",
    "valid",
    "split",
    "notes",
    "review_status",
    "reviewer",
    "reviewed_at_utc",
]


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--labels-out", required=True, type=Path)
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=173)
    args = parser.parse_args(list(argv))
    if args.count < 1:
        parser.error("--count must be at least 1")
    return args


def read_source_images(paths: list[Path]) -> list[Path]:
    images: list[Path] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError(f"{path} has no header")
            for row in reader:
                if row.get("valid", "true").strip().lower() not in {"true", "1", "yes"}:
                    continue
                image_path = Path(row["image_path"])
                if not image_path.is_absolute():
                    image_path = REPO_ROOT / image_path
                if image_path.exists():
                    images.append(image_path)
    if not images:
        raise ValueError("no source images found")
    return images


def transform_blur(image: Image.Image, rng: random.Random) -> Image.Image:
    return image.filter(ImageFilter.GaussianBlur(radius=rng.uniform(6.0, 14.0)))


def transform_exposure(image: Image.Image, rng: random.Random) -> Image.Image:
    factor = rng.choice([rng.uniform(0.05, 0.25), rng.uniform(3.0, 5.0)])
    return ImageEnhance.Brightness(image).enhance(factor)


def transform_occlusion(image: Image.Image, rng: random.Random) -> Image.Image:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    width, height = output.size
    left = rng.randint(width // 3, width * 2 // 3)
    top = rng.randint(height // 8, height // 3)
    right = rng.randint(left + width // 8, width)
    bottom = rng.randint(top + height // 8, height * 2 // 3)
    color = tuple(rng.randint(0, 20) for _ in range(3))
    draw.rectangle([left, top, right, bottom], fill=color)
    return output


def transform_partial(image: Image.Image, rng: random.Random) -> Image.Image:
    width, height = image.size
    crop_width = rng.randint(width // 2, width * 3 // 4)
    crop_height = rng.randint(height // 2, height * 3 // 4)
    left = rng.choice([0, width - crop_width])
    top = rng.choice([0, height - crop_height])
    partial = image.crop((left, top, left + crop_width, top + crop_height))
    output = Image.new("RGB", image.size, (0, 0, 0))
    output.paste(partial, (rng.randint(0, width - crop_width), rng.randint(0, height - crop_height)))
    return output


TRANSFORMS: tuple[tuple[str, Callable[[Image.Image, random.Random], Image.Image]], ...] = (
    ("blur", transform_blur),
    ("exposure", transform_exposure),
    ("occlusion", transform_occlusion),
    ("partial", transform_partial),
)


def generate(args: argparse.Namespace) -> list[dict[str, str]]:
    rng = random.Random(args.seed)
    sources = read_source_images(args.labels)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reviewed_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    rows: list[dict[str, str]] = []
    for index in range(args.count):
        source = sources[index % len(sources)]
        transform_name, transform = TRANSFORMS[index % len(TRANSFORMS)]
        with Image.open(source) as image:
            negative = transform(image.convert("RGB"), rng)
        sample_id = f"negative_{index + 1:04d}_{transform_name}"
        output_path = args.output_dir / f"{sample_id}.jpg"
        negative.save(output_path, quality=85)
        rows.append(
            {
                "sample_id": sample_id,
                "image_path": str(
                    output_path.relative_to(REPO_ROOT) if output_path.is_relative_to(REPO_ROOT) else output_path
                ),
                "temperature_c": "",
                "humidity_percent": "",
                "co2_ppm": "",
                "hcho_raw": "",
                "tvoc_raw": "",
                "valid": "false",
                "split": "test",
                "notes": f"auto_negative_{transform_name}",
                "review_status": "automated_consensus",
                "reviewer": "auto-consensus",
                "reviewed_at_utc": reviewed_at,
            }
        )
    return rows


def write_labels(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows = generate(args)
    write_labels(rows, args.labels_out)
    print(f"[INFO] wrote {len(rows)} negative labels to {args.labels_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
