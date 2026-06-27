#!/usr/bin/env python3
"""Capture one validated JPEG after each completed ESP32 measurement cycle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from PIL import Image

FIELDNAMES = [
    "sample_id",
    "image_path",
    "captured_at_utc",
    "lighting_label",
    "pipeline_cycle",
    "width",
    "height",
    "bytes",
    "sha256",
    "device_status",
    "device_confidence",
    "device_co2_ppm",
    "device_hcho_raw",
    "device_tvoc_raw",
    "device_temperature_c",
    "device_humidity_percent",
    "device_recognition_duration_ms",
    "framesize",
    "quality",
    "brightness",
    "contrast",
    "saturation",
    "aec",
    "agc",
    "awb",
]


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture once per completed firmware measurement cycle.",
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--count", type=int, default=520)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--lighting-label", default="unspecified")
    parser.add_argument("--framesize", choices=["qvga", "vga", "svga"], default="vga")
    parser.add_argument("--quality", type=int, default=8)
    parser.add_argument("--brightness", type=int, choices=range(-2, 3), default=2)
    parser.add_argument("--contrast", type=int, choices=range(-2, 3), default=2)
    parser.add_argument("--saturation", type=int, choices=range(-2, 3))
    parser.add_argument("--aec", type=int, choices=[0, 1], default=0)
    parser.add_argument("--agc", type=int, choices=[0, 1], default=0)
    parser.add_argument("--awb", type=int, choices=[0, 1], default=0)
    return parser.parse_args(list(argv))


def get_bytes(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "application/json,image/jpeg"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} from {url}")
        return response.read()


def get_json(url: str, timeout: float) -> dict[str, object]:
    return json.loads(get_bytes(url, timeout).decode("utf-8"))


def capture_query(args: argparse.Namespace) -> str:
    values: dict[str, object] = {
        "framesize": args.framesize,
        "quality": args.quality,
        "brightness": args.brightness,
        "contrast": args.contrast,
        "aec": args.aec,
        "agc": args.agc,
        "awb": args.awb,
    }
    if args.saturation is not None:
        values["saturation"] = args.saturation
    return urllib.parse.urlencode(values)


def existing_rows(manifest: Path) -> list[dict[str, str]]:
    if not manifest.exists():
        return []
    with manifest.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def append_row(manifest: Path, row: dict[str, object]) -> None:
    new_file = not manifest.exists()
    with manifest.open("a", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        csv_file.flush()


def validate_jpeg(data: bytes, framesize: str) -> tuple[int, int]:
    expected = {"qvga": (320, 240), "vga": (640, 480), "svga": (800, 600)}[framesize]
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.format != "JPEG":
            raise ValueError(f"expected JPEG, got {image.format}")
        if image.size != expected:
            raise ValueError(f"expected {expected[0]}x{expected[1]}, got {image.width}x{image.height}")
        return image.size


def value(payload: dict[str, object], name: str) -> object:
    result = payload.get(name)
    return "" if result is None else result


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.count <= 0:
        raise SystemExit("--count must be positive")
    base_url = args.base_url.rstrip("/")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "manifest.csv"
    rows = existing_rows(manifest)
    accepted = len(rows)
    last_cycle = max((int(row["pipeline_cycle"]) for row in rows), default=-1)
    query = capture_query(args)
    print(f"[INFO] output={args.output} accepted={accepted} target={args.count}", flush=True)

    while accepted < args.count:
        try:
            status = get_json(f"{base_url}/api/v1/status", args.timeout_seconds)
            cycle = int(status.get("pipeline_cycle", 0))
            if status.get("pipeline_stage") != "waiting" or cycle <= last_cycle:
                time.sleep(args.poll_seconds)
                continue

            current = get_json(f"{base_url}/api/v1/current", args.timeout_seconds)
            data = get_bytes(f"{base_url}/debug/capture.jpg?{query}", args.timeout_seconds)
            width, height = validate_jpeg(data, args.framesize)
            sample_id = f"capture_{accepted + 1:04d}"
            relative_path = args.output / f"{sample_id}.jpg"
            relative_path.write_bytes(data)
            row = {
                "sample_id": sample_id,
                "image_path": relative_path,
                "captured_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "lighting_label": args.lighting_label,
                "pipeline_cycle": cycle,
                "width": width,
                "height": height,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "device_status": value(current, "status"),
                "device_confidence": value(current, "confidence"),
                "device_co2_ppm": value(current, "co2_ppm"),
                "device_hcho_raw": value(current, "hcho_raw"),
                "device_tvoc_raw": value(current, "tvoc_raw"),
                "device_temperature_c": value(current, "temperature_c"),
                "device_humidity_percent": value(current, "humidity_percent"),
                "device_recognition_duration_ms": value(current, "recognition_duration_ms"),
                "framesize": args.framesize,
                "quality": args.quality,
                "brightness": args.brightness,
                "contrast": args.contrast,
                "saturation": "" if args.saturation is None else args.saturation,
                "aec": args.aec,
                "agc": args.agc,
                "awb": args.awb,
            }
            append_row(manifest, row)
            accepted += 1
            last_cycle = cycle
            print(
                f"[INFO] {sample_id} cycle={cycle} bytes={len(data)} "
                f"device={row['device_co2_ppm']}/{row['device_temperature_c']}/{row['device_humidity_percent']}",
                flush=True,
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            print(f"[WARN] acquisition retry: {error}", file=sys.stderr, flush=True)
            time.sleep(max(args.poll_seconds, 0.5))

    print(f"[INFO] captured {accepted} validated images in {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
