#!/usr/bin/env python3
"""Audit camera captures before labeling or model training."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.model_training.build_digit_dataset import DisplayBounds, locate_display  # noqa: E402

EXPECTED_SIZE = (640, 480)
IMAGE_SUFFIXES = {".jpg", ".jpeg"}


@dataclass
class AuditRow:
    image_path: str
    accepted: bool = False
    rejection_reasons: str = ""
    decode_ok: bool = False
    jpeg_format: bool = False
    width: int | None = None
    height: int | None = None
    locator_found: bool = False
    locator_x: int | None = None
    locator_y: int | None = None
    locator_width: int | None = None
    locator_height: int | None = None
    locator_rotation: int | None = None
    locator_score: int | None = None
    brightness_mean: float | None = None
    contrast_stddev: float | None = None
    sharpness_laplacian_variance: float | None = None
    perceptual_dhash: str = ""
    nearest_accepted_path: str = ""
    nearest_hash_distance: int | None = None


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit VGA JPEG captures for localization, image quality, and duplicates."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="JPEG paths or directories to scan recursively")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-accepted", type=int, default=1)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--min-brightness", type=float, default=15.0)
    parser.add_argument("--max-brightness", type=float, default=240.0)
    parser.add_argument("--min-contrast", type=float, default=18.0)
    parser.add_argument("--min-sharpness", type=float, default=30.0)
    parser.add_argument(
        "--duplicate-distance",
        type=int,
        default=2,
        help="Reject hashes at or below this Hamming distance; use -1 to disable",
    )
    args = parser.parse_args(list(argv))
    if args.min_accepted < 0:
        parser.error("--min-accepted must be nonnegative")
    if args.min_brightness > args.max_brightness:
        parser.error("--min-brightness cannot exceed --max-brightness")
    if args.duplicate_distance > 64:
        parser.error("--duplicate-distance cannot exceed 64")
    return args


def discover_images(inputs: Iterable[Path]) -> tuple[list[Path], list[Path]]:
    images: dict[Path, Path] = {}
    missing: list[Path] = []
    for input_path in inputs:
        path = input_path.expanduser()
        if not path.exists():
            missing.append(path)
            continue
        if path.is_file():
            resolved = path.resolve()
            images.setdefault(resolved, path)
            continue
        candidates = path.rglob("*")
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() in IMAGE_SUFFIXES:
                resolved = candidate.resolve()
                images.setdefault(resolved, candidate)
    return sorted(images), missing


def display_region(image: Image.Image, bounds: DisplayBounds | None) -> Image.Image:
    if bounds is None:
        return image
    oriented = image.rotate(bounds.rotation) if bounds.rotation else image
    return oriented.crop((bounds.x, bounds.y, bounds.x + bounds.width, bounds.y + bounds.height))


def image_metrics(image: Image.Image) -> tuple[float, float, float]:
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    if min(gray.shape) < 3:
        sharpness = 0.0
    else:
        laplacian = (
            -4.0 * gray[1:-1, 1:-1]
            + gray[:-2, 1:-1]
            + gray[2:, 1:-1]
            + gray[1:-1, :-2]
            + gray[1:-1, 2:]
        )
        sharpness = float(np.var(laplacian))
    return brightness, contrast, sharpness


def perceptual_dhash(image: Image.Image) -> int:
    sample = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = np.asarray(sample, dtype=np.int16)
    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bit)
    return value


def hash_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def audit_image(path: Path, args: argparse.Namespace) -> tuple[AuditRow, int | None]:
    row = AuditRow(image_path=str(path))
    reasons: list[str] = []
    try:
        with Image.open(path) as probe:
            row.jpeg_format = probe.format == "JPEG"
            probe.verify()
        with Image.open(path) as opened:
            opened.load()
            image = opened.convert("RGB")
            row.width, row.height = image.size
        row.decode_ok = True
    except (OSError, UnidentifiedImageError, ValueError) as error:
        row.rejection_reasons = f"decode_error:{type(error).__name__}"
        return row, None

    if not row.jpeg_format:
        reasons.append("not_jpeg")
    if image.size != EXPECTED_SIZE:
        reasons.append("invalid_dimensions")

    bounds = locate_display(image)
    if bounds is None:
        reasons.append("display_not_found")
    else:
        row.locator_found = True
        row.locator_x = bounds.x
        row.locator_y = bounds.y
        row.locator_width = bounds.width
        row.locator_height = bounds.height
        row.locator_rotation = bounds.rotation
        row.locator_score = bounds.score

    region = display_region(image, bounds)
    row.brightness_mean, row.contrast_stddev, row.sharpness_laplacian_variance = image_metrics(region)
    if row.brightness_mean < args.min_brightness:
        reasons.append("brightness_too_low")
    if row.brightness_mean > args.max_brightness:
        reasons.append("brightness_too_high")
    if row.contrast_stddev < args.min_contrast:
        reasons.append("contrast_too_low")
    if row.sharpness_laplacian_variance < args.min_sharpness:
        reasons.append("sharpness_too_low")

    image_hash = perceptual_dhash(region)
    row.perceptual_dhash = f"{image_hash:016x}"
    row.rejection_reasons = ";".join(reasons)
    return row, image_hash


def audit_paths(paths: Iterable[Path], missing: Iterable[Path], args: argparse.Namespace) -> list[AuditRow]:
    rows = [AuditRow(image_path=str(path), rejection_reasons="path_not_found") for path in missing]
    accepted_hashes: list[tuple[int, str]] = []
    for path in paths:
        row, image_hash = audit_image(path, args)
        if image_hash is not None and not row.rejection_reasons and args.duplicate_distance >= 0:
            nearest = min(
                (
                    (hash_distance(image_hash, accepted_hash), accepted_path)
                    for accepted_hash, accepted_path in accepted_hashes
                ),
                default=None,
            )
            if nearest is not None:
                row.nearest_hash_distance, row.nearest_accepted_path = nearest
                if row.nearest_hash_distance <= args.duplicate_distance:
                    row.rejection_reasons = "near_duplicate"
        row.accepted = not row.rejection_reasons
        if row.accepted and image_hash is not None:
            accepted_hashes.append((image_hash, row.image_path))
        rows.append(row)
    return rows


def write_csv(rows: list[AuditRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(AuditRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def metric_summary(rows: list[AuditRow], field: str) -> dict[str, float] | None:
    values = np.asarray(
        [getattr(row, field) for row in rows if getattr(row, field) is not None], dtype=np.float64
    )
    if not len(values):
        return None
    return {
        "min": float(np.min(values)),
        "p10": float(np.percentile(values, 10)),
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "max": float(np.max(values)),
    }


def build_report(rows: list[AuditRow], args: argparse.Namespace) -> dict[str, object]:
    reason_counts: dict[str, int] = {}
    for row in rows:
        for reason in filter(None, row.rejection_reasons.split(";")):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    accepted = sum(row.accepted for row in rows)
    return {
        "tool": "dataset.audit_capture_corpus",
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "expected_dimensions": {"width": EXPECTED_SIZE[0], "height": EXPECTED_SIZE[1]},
        "thresholds": {
            "minimum_accepted": args.min_accepted,
            "brightness": {"minimum": args.min_brightness, "maximum": args.max_brightness},
            "minimum_contrast": args.min_contrast,
            "minimum_sharpness": args.min_sharpness,
            "maximum_near_duplicate_hash_distance": args.duplicate_distance,
        },
        "counts": {"scanned": len(rows), "accepted": accepted, "rejected": len(rows) - accepted},
        "rejection_reasons": dict(sorted(reason_counts.items())),
        "metrics": {
            "brightness_mean": metric_summary(rows, "brightness_mean"),
            "contrast_stddev": metric_summary(rows, "contrast_stddev"),
            "sharpness_laplacian_variance": metric_summary(rows, "sharpness_laplacian_variance"),
        },
        "strict_threshold_met": accepted >= args.min_accepted,
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    paths, missing = discover_images(args.inputs)
    rows = audit_paths(paths, missing, args)
    output_dir = args.output_dir.resolve()
    csv_path = output_dir / "capture_corpus_audit.csv"
    json_path = output_dir / "capture_corpus_audit.json"
    write_csv(rows, csv_path)
    report = build_report(rows, args)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = report["counts"]
    print(f"[INFO] scanned={counts['scanned']} accepted={counts['accepted']} rejected={counts['rejected']}")
    print(f"[INFO] wrote {csv_path}")
    print(f"[INFO] wrote {json_path}")
    if args.strict and not report["strict_threshold_met"]:
        print(
            f"[ERROR] accepted count {counts['accepted']} is below required {args.min_accepted}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
