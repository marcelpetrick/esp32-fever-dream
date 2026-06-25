#!/usr/bin/env python3
"""Label and benchmark a fixed-layout ESP32-CAM display capture batch.

This tool is for the first acquisition loop. It records human-confirmed
temperature and humidity labels for a capture directory, crops the fixed ROIs,
and writes simple image-quality metrics that tell us whether the dataset is
useful for the next OCR/modeling step.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageStat

TEMP_ROI = (245, 293, 370, 350)
HUMIDITY_ROI = (430, 292, 570, 350)
BOTTOM_STRIP_ROI = (120, 285, 620, 430)


@dataclass(frozen=True)
class RoiMetrics:
    brightness: float
    contrast: float
    sharpness: float


@dataclass(frozen=True)
class SampleLabel:
    sample_id: str
    image_path: Path
    lighting_label: str
    split: str
    temperature_text: str
    temperature_c: float
    humidity_percent: int
    valid: bool
    confidence: float
    roi_quality: RoiMetrics
    notes: str


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create labels and fixed-layout benchmark artifacts for a capture batch.",
    )
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--temperature-c", required=True, type=float)
    parser.add_argument("--humidity-percent", required=True, type=int)
    parser.add_argument("--temperature-unit", default="C", choices=["C", "F"])
    parser.add_argument("--output", type=Path, help="Labels CSV output path.")
    parser.add_argument("--report-json", type=Path, help="Quality report JSON path.")
    parser.add_argument("--report-md", type=Path, help="Quality report Markdown path.")
    parser.add_argument(
        "--contact-sheet", type=Path, help="Bottom-strip contact sheet path."
    )
    parser.add_argument(
        "--method-note",
        default="human_confirmed_fixed_layout_baseline",
        help="Method note written to labels.",
    )
    return parser.parse_args(list(argv))


def read_manifest(dataset_dir: Path) -> list[dict[str, str]]:
    manifest = dataset_dir / "manifest.csv"
    with manifest.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{manifest} is empty")
        return list(reader)


def luminance(image: Image.Image) -> Image.Image:
    return image.convert("L")


def mean_abs_neighbor_delta(gray: Image.Image) -> float:
    pixels = gray.load()
    width, height = gray.size
    if width < 2 or height < 2:
        return 0.0

    total = 0
    count = 0
    for y in range(height - 1):
        for x in range(width - 1):
            value = pixels[x, y]
            total += abs(value - pixels[x + 1, y])
            total += abs(value - pixels[x, y + 1])
            count += 2
    return total / count


def roi_metrics(image: Image.Image, roi: tuple[int, int, int, int]) -> RoiMetrics:
    gray = luminance(image.crop(roi))
    stat = ImageStat.Stat(gray)
    return RoiMetrics(
        brightness=stat.mean[0],
        contrast=stat.stddev[0],
        sharpness=mean_abs_neighbor_delta(gray),
    )


def confidence_from_metrics(metrics: RoiMetrics) -> float:
    contrast_score = min(metrics.contrast / 45.0, 1.0)
    sharpness_score = min(metrics.sharpness / 18.0, 1.0)
    brightness_score = 1.0 - min(abs(metrics.brightness - 70.0) / 90.0, 1.0)
    return max(
        0.0,
        min(
            (0.45 * contrast_score)
            + (0.45 * sharpness_score)
            + (0.10 * brightness_score),
            1.0,
        ),
    )


def split_for_index(index: int) -> str:
    if index % 10 == 0:
        return "test"
    if index % 5 == 0:
        return "validation"
    return "train"


def label_rows(
    args: argparse.Namespace, manifest_rows: list[dict[str, str]]
) -> list[SampleLabel]:
    labels: list[SampleLabel] = []
    temp_text = f"{args.temperature_c:g}{args.temperature_unit}"
    valid = args.temperature_unit == "C"

    for index, row in enumerate(manifest_rows, start=1):
        if row.get("http_code") != "200":
            continue

        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = Path.cwd() / image_path
        image = Image.open(image_path).convert("RGB")

        temp_metrics = roi_metrics(image, TEMP_ROI)
        humidity_metrics = roi_metrics(image, HUMIDITY_ROI)
        combined_metrics = RoiMetrics(
            brightness=(temp_metrics.brightness + humidity_metrics.brightness) / 2.0,
            contrast=(temp_metrics.contrast + humidity_metrics.contrast) / 2.0,
            sharpness=(temp_metrics.sharpness + humidity_metrics.sharpness) / 2.0,
        )
        confidence = confidence_from_metrics(combined_metrics)
        notes = args.method_note
        if args.temperature_unit != "C":
            notes += ";unit_warning_not_celsius"
        if confidence < 0.45:
            notes += ";low_roi_quality"

        labels.append(
            SampleLabel(
                sample_id=row["sample_id"],
                image_path=Path(row["image_path"]),
                lighting_label=row.get("lighting_label", ""),
                split=split_for_index(index),
                temperature_text=temp_text,
                temperature_c=args.temperature_c,
                humidity_percent=args.humidity_percent,
                valid=valid,
                confidence=confidence,
                roi_quality=combined_metrics,
                notes=notes,
            )
        )

    return labels


def write_labels(labels: list[SampleLabel], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "sample_id",
                "image_path",
                "lighting_label",
                "split",
                "display_text",
                "predicted_display_text",
                "temperature_text",
                "temperature_c",
                "humidity_percent",
                "valid",
                "confidence",
                "roi_brightness",
                "roi_contrast",
                "roi_sharpness",
                "notes",
            ],
        )
        writer.writeheader()
        for label in labels:
            display_text = f"{label.temperature_text} {label.humidity_percent}%"
            writer.writerow(
                {
                    "sample_id": label.sample_id,
                    "image_path": label.image_path,
                    "lighting_label": label.lighting_label,
                    "split": label.split,
                    "display_text": display_text,
                    "predicted_display_text": display_text,
                    "temperature_text": label.temperature_text,
                    "temperature_c": f"{label.temperature_c:.2f}",
                    "humidity_percent": label.humidity_percent,
                    "valid": str(label.valid).lower(),
                    "confidence": f"{label.confidence:.4f}",
                    "roi_brightness": f"{label.roi_quality.brightness:.2f}",
                    "roi_contrast": f"{label.roi_quality.contrast:.2f}",
                    "roi_sharpness": f"{label.roi_quality.sharpness:.2f}",
                    "notes": label.notes,
                }
            )


def percentile(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return ordered[index]


def summarize(
    labels: list[SampleLabel], source_dir: Path, labels_path: Path
) -> dict[str, object]:
    confidences = [label.confidence for label in labels]
    contrasts = [label.roi_quality.contrast for label in labels]
    sharpness = [label.roi_quality.sharpness for label in labels]
    low_quality = [label.sample_id for label in labels if label.confidence < 0.45]
    split_counts: dict[str, int] = {}
    for label in labels:
        split_counts[label.split] = split_counts.get(label.split, 0) + 1

    return {
        "tool": "dataset.label_fixed_display_batch",
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "source_dir": str(source_dir),
        "labels_csv": str(labels_path),
        "method": "human-confirmed fixed-layout baseline labels plus ROI quality metrics",
        "summary": {
            "rows": len(labels),
            "split_counts": dict(sorted(split_counts.items())),
            "temperature_text": labels[0].temperature_text if labels else "",
            "temperature_c": labels[0].temperature_c if labels else None,
            "humidity_percent": labels[0].humidity_percent if labels else None,
            "minimum_confidence": min(confidences) if confidences else None,
            "median_confidence": (
                statistics.median(confidences) if confidences else None
            ),
            "p10_confidence": percentile(confidences, 0.10) if confidences else None,
            "median_roi_contrast": statistics.median(contrasts) if contrasts else None,
            "median_roi_sharpness": statistics.median(sharpness) if sharpness else None,
            "low_quality_count": len(low_quality),
        },
        "low_quality_samples": low_quality[:50],
        "limitations": [
            "All baseline labels have the same temperature and humidity values.",
            "The predicted_display_text column is a fixed-layout baseline predictor, not a trained OCR model.",
            "A useful TinyML digit classifier still needs captures where the displayed values vary.",
        ],
    }


def render_report(report: dict[str, object]) -> str:
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# Fixed Display Batch Report",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Source directory: `{report['source_dir']}`",
        f"Labels CSV: `{report['labels_csv']}`",
        f"Method: {report['method']}",
        "",
        "## Summary",
        "",
        f"- Rows: {summary['rows']}",
        f"- Splits: {summary['split_counts']}",
        f"- Temperature label: `{summary['temperature_text']}`",
        f"- Temperature Celsius: `{summary['temperature_c']}`",
        f"- Humidity percent: `{summary['humidity_percent']}`",
        f"- Minimum ROI confidence: `{summary['minimum_confidence']:.4f}`",
        f"- Median ROI confidence: `{summary['median_confidence']:.4f}`",
        f"- P10 ROI confidence: `{summary['p10_confidence']:.4f}`",
        f"- Median ROI contrast: `{summary['median_roi_contrast']:.2f}`",
        f"- Median ROI sharpness: `{summary['median_roi_sharpness']:.2f}`",
        f"- Low-quality samples: `{summary['low_quality_count']}`",
        "",
        "## Limitations",
        "",
    ]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: dict[str, object], json_path: Path, markdown_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_report(report), encoding="utf-8")


def write_contact_sheet(dataset_dir: Path, output: Path) -> None:
    images = sorted(dataset_dir.glob("capture_*.jpg"))
    selected = (
        images[:12]
        if len(images) <= 12
        else [images[round(i * (len(images) - 1) / 11)] for i in range(12)]
    )
    cells: list[Image.Image] = []
    for image_path in selected:
        image = Image.open(image_path).convert("RGB")
        crop = image.crop(BOTTOM_STRIP_ROI)
        crop.thumbnail((500, 145))
        canvas = Image.new("RGB", (500, 165), "white")
        canvas.paste(crop, (0, 0))
        ImageDraw.Draw(canvas).text((4, 148), image_path.stem, fill=(0, 0, 0))
        cells.append(canvas)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (500, 165 * len(cells)), "white")
    for index, cell in enumerate(cells):
        sheet.paste(cell, (0, index * 165))
    sheet.save(output, quality=95)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    dataset_dir = args.dataset_dir.resolve()
    labels_path = args.output or dataset_dir / "labels_environment.csv"
    report_json = args.report_json or dataset_dir / "fixed_display_report.json"
    report_md = args.report_md or dataset_dir / "fixed_display_report.md"
    contact_sheet = (
        args.contact_sheet or dataset_dir / "bottom_strip_contact_labeled.jpg"
    )

    manifest_rows = read_manifest(dataset_dir)
    labels = label_rows(args, manifest_rows)
    if not labels:
        raise SystemExit(f"{dataset_dir} has no successful captures to label")

    write_labels(labels, labels_path)
    report = summarize(labels, dataset_dir, labels_path)
    write_report(report, report_json, report_md)
    write_contact_sheet(dataset_dir, contact_sheet)

    print(f"[INFO] wrote {labels_path}")
    print(f"[INFO] wrote {report_md}")
    print(f"[INFO] wrote {contact_sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
