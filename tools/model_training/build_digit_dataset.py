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

RELATIVE_TEMP_DIGIT_BOXES_ROTATED = {
    0: (630, 6535, 890, 1140),
    1: (1595, 6535, 890, 1140),
}
RELATIVE_TEMP_DIGIT_BOXES_UPRIGHT = {
    0: (1540, 6535, 760, 1140),
    1: (2400, 6535, 760, 1140),
}
RELATIVE_TEMP_DIGIT_BOXES = RELATIVE_TEMP_DIGIT_BOXES_ROTATED
RELATIVE_HUMIDITY_DIGIT_BOXES = {
    0: (7630, 6535, 890, 1140),
    1: (8595, 6535, 890, 1140),
}
RELATIVE_CO2_DIGIT_BOXES = {
    0: (2110, 750, 925, 1360),
    1: (3110, 750, 925, 1360),
    2: (4110, 750, 925, 1360),
    3: (5110, 750, 925, 1360),
}
RELATIVE_HCHO_DIGIT_BOXES = {
    0: (2185, 2605, 815, 1070),
    1: (3185, 2605, 815, 1070),
    2: (4185, 2605, 815, 1070),
    3: (5185, 2605, 815, 1070),
}
RELATIVE_TVOC_DIGIT_BOXES = {
    0: (2185, 4390, 815, 1070),
    1: (3185, 4390, 815, 1070),
    2: (4185, 4390, 815, 1070),
    3: (5185, 4390, 815, 1070),
}

TEMP_DIGIT_BOXES = {
    0: (495, 87, 519, 119),
    1: (470, 87, 494, 119),
}
HUMIDITY_DIGIT_BOXES = {
    0: (323, 87, 347, 119),
    1: (297, 87, 321, 119),
}
CO2_DIGIT_BOXES = {
    0: (466, 243, 491, 282),
    1: (439, 243, 464, 282),
    2: (412, 243, 437, 282),
    3: (385, 243, 410, 282),
}
HCHO_DIGIT_BOXES = {
    0: (469, 199, 491, 231),
    1: (442, 199, 464, 231),
    2: (415, 199, 437, 231),
    3: (388, 199, 410, 231),
}
TVOC_DIGIT_BOXES = {
    0: (469, 149, 491, 181),
    1: (442, 149, 464, 181),
    2: (415, 149, 437, 181),
    3: (388, 149, 410, 181),
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


@dataclass(frozen=True)
class DisplayBounds:
    x: int
    y: int
    width: int
    height: int
    rotation: int
    score: int


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
    untrusted: list[str] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError(f"{path} has no header")
            for row in reader:
                review_status = row.get("review_status", "").strip().lower()
                is_untrusted = (
                    "proposal_status" in row
                    or (review_status and review_status not in {"approved", "corrected", "human"})
                    or (not review_status and "ollama_ocr" in row.get("notes", "").lower())
                )
                if is_untrusted:
                    untrusted.append(f"{path}:{row.get('sample_id', '?')}")
                    continue
                row["_labels_path"] = str(path)
                rows.append(row)
    if untrusted:
        preview = ", ".join(untrusted[:5])
        raise ValueError(
            f"refusing {len(untrusted)} unreviewed automated labels; "
            f"promote proposals through review_ollama_labels.py first ({preview})"
        )
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


def is_color_strip_pixel(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    maximum = max(pixel)
    minimum = min(pixel)
    luma = (r * 30 + g * 59 + b * 11) // 100
    if luma < 35 or maximum - minimum < 35 or b > max(r, g) + 25:
        return False
    return (g > 70 and r > 35) or (r > 95 and g > 35)


def is_bright_text_pixel(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    maximum = max(pixel)
    minimum = min(pixel)
    luma = (r * 30 + g * 59 + b * 11) // 100
    return luma > 95 and maximum - minimum < 105


def locate_bounds_for_orientation(image: Image.Image, rotation: int) -> DisplayBounds | None:
    oriented = image.rotate(rotation) if rotation else image
    width, height = oriented.size
    pixels = oriented.load()
    row_counts = [0] * height
    for y in range(0, height, 2):
        count = 0
        for x in range(0, width, 2):
            if is_color_strip_pixel(pixels[x, y]):
                count += 1
        row_counts[y] = count
    strip_row = max(range(0, height, 2), key=lambda y: row_counts[y])
    best_count = row_counts[strip_row]
    if best_count < 20:
        return None
    if strip_row < height * 35 // 100:
        return None

    strip_threshold = max(8, best_count // 3)
    strip_top = strip_row
    strip_bottom = strip_row
    for y in range(strip_row, -1, -2):
        if row_counts[y] < strip_threshold:
            break
        strip_top = y
    for y in range(strip_row, height, 2):
        if row_counts[y] < strip_threshold:
            break
        strip_bottom = y

    color_xs: list[int] = []
    for y in range(max(0, strip_top - 4), min(height - 1, strip_bottom + 4) + 1, 2):
        for x in range(0, width, 2):
            if is_color_strip_pixel(pixels[x, y]):
                color_xs.append(x)
    if len(color_xs) < 60:
        return None
    color_min_x = min(color_xs)
    color_max_x = max(color_xs)
    if color_min_x >= color_max_x:
        return None

    x_margin = max(80, color_max_x - color_min_x)
    scan_min_x = max(0, color_min_x - x_margin)
    scan_max_x = min(width - 1, color_max_x + x_margin)
    text_xs: list[int] = []
    text_ys: list[int] = []
    for y in range(0, max(0, strip_top - 10), 2):
        for x in range(scan_min_x, scan_max_x + 1, 2):
            if is_bright_text_pixel(pixels[x, y]):
                text_xs.append(x)
                text_ys.append(y)
    if len(text_xs) < 120:
        return None

    text_min_y = min(text_ys)
    text_max_y = max(text_ys)
    if text_min_y >= strip_top or text_max_y >= strip_top:
        return None

    strip_width = color_max_x - color_min_x + 1
    final_width = min(max(strip_width * 17 // 10, 160), width)
    final_height = min(max(strip_width * 18 // 10, 150), height)
    min_x = color_min_x - final_width // 12
    max_y = strip_bottom + max(8, final_height // 14)
    min_x = min(max(0, min_x), max(0, width - final_width))
    max_y = min(max(final_height - 1, max_y), height - 1)
    min_y = max_y - final_height + 1
    if (
        final_width < 140
        or final_width > width - 20
        or final_height < 140
        or final_height > height - 20
    ):
        return None
    return DisplayBounds(min_x, min_y, final_width, final_height, rotation, len(color_xs) + len(text_xs))


def locate_display(image: Image.Image) -> DisplayBounds | None:
    candidates = [
        candidate
        for candidate in (locate_bounds_for_orientation(image, 0), locate_bounds_for_orientation(image, 180))
        if candidate is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.score)


def resolve_relative_box(bounds: DisplayBounds, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, width, height = box
    left = bounds.x + (bounds.width * x // 10000)
    top = bounds.y + (bounds.height * y // 10000)
    right = left + max(8, bounds.width * width // 10000)
    bottom = top + max(12, bounds.height * height // 10000)
    return left, top, right, bottom


def crop_digit(
    image: Image.Image,
    bounds: DisplayBounds | None,
    relative_box: tuple[int, int, int, int],
    fallback_box: tuple[int, int, int, int],
) -> Image.Image:
    if bounds is None:
        return image.crop(fallback_box)
    oriented = image.rotate(bounds.rotation) if bounds.rotation else image
    return oriented.crop(resolve_relative_box(bounds, relative_box))


def relative_temp_boxes(bounds: DisplayBounds | None) -> dict[int, tuple[int, int, int, int]]:
    if bounds is not None and bounds.rotation == 0:
        return RELATIVE_TEMP_DIGIT_BOXES_UPRIGHT
    return RELATIVE_TEMP_DIGIT_BOXES_ROTATED


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

        image = Image.open(image_path).convert("RGB")
        bounds = locate_display(image)
        digit_groups: list[
            tuple[str, str, dict[int, tuple[int, int, int, int]], dict[int, tuple[int, int, int, int]]]
        ] = []
        if row.get("co2_ppm"):
            digit_groups.append(("co2", f"{int(row['co2_ppm']):04d}"[-4:], RELATIVE_CO2_DIGIT_BOXES, CO2_DIGIT_BOXES))
        if row.get("hcho_raw"):
            digit_groups.append(
                ("hcho", f"{int(row['hcho_raw']):04d}"[-4:], RELATIVE_HCHO_DIGIT_BOXES, HCHO_DIGIT_BOXES)
            )
        if row.get("tvoc_raw"):
            digit_groups.append(
                ("tvoc", f"{int(row['tvoc_raw']):04d}"[-4:], RELATIVE_TVOC_DIGIT_BOXES, TVOC_DIGIT_BOXES)
            )
        temperature = f"{float(row['temperature_c']):.0f}".zfill(2)[-2:]
        humidity = f"{int(row['humidity_percent']):02d}"[-2:]
        digit_groups.extend(
            (
                ("temp", temperature, relative_temp_boxes(bounds), TEMP_DIGIT_BOXES),
                ("humidity", humidity, RELATIVE_HUMIDITY_DIGIT_BOXES, HUMIDITY_DIGIT_BOXES),
            )
        )
        split = row.get("split") or split_for_index(
            row_index, args.real_test_every, args.real_validation_every
        )
        for prefix, text, relative_boxes, fallback_boxes in digit_groups:
            for position, digit in enumerate(text):
                crop = normalize_crop(crop_digit(image, bounds, relative_boxes[position], fallback_boxes[position]))
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
