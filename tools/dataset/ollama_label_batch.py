#!/usr/bin/env python3
"""Auto-label AQS display captures using an Ollama vision model.

Reads the manifest.csv in a capture directory, queries the configured
Ollama vision model for each accepted frame, extracts the five AQS values
(CO2 ppm, HCHO raw, TVOC raw, temperature °C, humidity %), and writes a
labels_environment.csv compatible with the existing training pipeline.

Usage:
    python3 tools/dataset/ollama_label_batch.py \\
        --dataset-dir tools/dataset/captures/serial_timed_fast_20260627T1205Z \\
        --model llama3.2-vision:11b \\
        --output tools/dataset/captures/serial_timed_fast_20260627T1205Z/labels_environment.csv

    # Alternative faster model:
    python3 tools/dataset/ollama_label_batch.py \\
        --dataset-dir tools/dataset/captures/serial_timed_fast_20260627T1205Z \\
        --model qwen3-vl:4b

Requires ollama running locally with a vision-capable model pulled.
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

OLLAMA_URL = "http://localhost:11434/api/generate"

# On integrated GPUs (e.g. Intel Iris Xe) vision model inference takes
# 60-120 s per frame once warm; cold start adds 60-200 s for model loading.
# 360 s covers both without triggering a premature client-side timeout that
# leaves stuck requests in Ollama's internal queue.
REQUEST_TIMEOUT_SECONDS = 360

# Smallest prompt that forces the model to load into VRAM without touching
# the real batch.
_WARMUP_PROMPT = "Reply with the single word: ready"

OUTPUT_FIELDNAMES = [
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
]

# Plausibility ranges for validation.
CO2_RANGE = (300, 9999)
HCHO_RANGE = (0, 999)
TVOC_RANGE = (0, 999)
TEMP_RANGE = (-10, 60)
HUM_RANGE = (0, 100)

_PROMPT = """\
/no_think This photograph shows an air quality sensor LCD display. The display has these rows:
Row 1 (top):   CO2 label, then large 3-4 digit integer in ppm (typical range 400-2000). Read ALL digits.
Row 2:         HCHO label, then a decimal like 0.013 mg/m³. Return only the integer after the decimal (0.013 → 13).
Row 3:         TVOC label, then a decimal like 0.036 mg/m³. Return only the integer after the decimal (0.036 → 36).
Row 4 left:    thermometer icon then 2-digit temperature then °C symbol.
Row 4 right:   droplet icon then 2-digit humidity then % symbol.

Return ONLY a single valid JSON object with these exact keys, no other text:
{"co2_ppm":INTEGER,"hcho_raw":INTEGER,"tvoc_raw":INTEGER,"temperature_c":INTEGER,"humidity_percent":INTEGER,"valid":true}

If the display is not readable or any value is unclear, set "valid" to false and use -1 for unknown fields."""


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-label AQS display captures via Ollama vision OCR.",
    )
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path. Defaults to labels_environment.csv inside --dataset-dir.",
    )
    parser.add_argument(
        "--model",
        default="qwen3-vl:4b",
        help="Ollama vision model name (default: qwen3-vl:4b).",
    )
    parser.add_argument(
        "--no-warmup",
        dest="warmup",
        action="store_false",
        help="Skip the model warm-up call before batch processing.",
    )
    parser.set_defaults(warmup=True)
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=2048,
        help=(
            "Context window size sent to Ollama (default: 2048). "
            "Smaller values reduce VRAM usage and allow more layers to be "
            "offloaded to GPU — 2048 is enough for vision + short output. "
            "Also triggers Ollama's flash-attention path."
        ),
    )
    parser.add_argument(
        "--ollama-url",
        default=OLLAMA_URL,
        help="Ollama API base URL.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retry attempts per image on JSON parse failure (default: 3).",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=REQUEST_TIMEOUT_SECONDS,
        help=f"Ollama HTTP request timeout in seconds (default: {REQUEST_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--inter-request-delay",
        type=float,
        default=1.0,
        help="Seconds to sleep between requests to avoid hammering Ollama (default: 1.0).",
    )
    parser.add_argument(
        "--train-fraction",
        type=float,
        default=0.80,
        help="Fraction of accepted frames assigned to the train split (default: 0.80).",
    )
    parser.add_argument(
        "--val-fraction",
        type=float,
        default=0.10,
        help="Fraction assigned to validation (default: 0.10). Remainder is test.",
    )
    parser.add_argument(
        "--skip-duplicates",
        action="store_true",
        default=True,
        help="Skip frames the manifest marks as duplicate (default: True).",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Re-label all frames even if the output CSV already exists.",
    )
    parser.set_defaults(resume=True)
    parser.add_argument(
        "--lighting-label",
        default="",
        help="Optional lighting label written to the notes field.",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        default=True,
        help="Process unlabeled frames in random order (default: on). "
             "Randomising spreads sampling across the full capture window so "
             "rare digit values appear early rather than after all similar "
             "consecutive frames have been processed.",
    )
    parser.add_argument(
        "--no-shuffle",
        dest="shuffle",
        action="store_false",
        help="Process frames in manifest order instead of randomly.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible shuffle (default: random).",
    )
    return parser.parse_args(list(argv))


def load_manifest(dataset_dir: Path) -> list[dict[str, str]]:
    manifest_path = dataset_dir / "manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.csv in {dataset_dir}")
    with manifest_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f"{manifest_path} is empty")
    return rows


def accepted_rows(rows: list[dict[str, str]], skip_duplicates: bool) -> list[dict[str, str]]:
    """Return manifest rows that have an actual saved image."""
    accepted: list[dict[str, str]] = []
    for row in rows:
        status = row.get("serial_status") or row.get("http_code") or ""
        if skip_duplicates and status.lower() in ("duplicate", "failed"):
            continue
        # Require a non-zero byte count as extra guard.
        try:
            if int(row.get("bytes", 0)) == 0:
                continue
        except ValueError:
            continue
        accepted.append(row)
    return accepted


def load_existing_labels(output_path: Path) -> set[str]:
    """Return sample_ids already written to the output CSV."""
    if not output_path.exists():
        return set()
    with output_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["sample_id"] for row in reader}


def warmup_model(model: str, url: str, timeout: int, num_ctx: int) -> None:
    """Send a tiny text-only prompt to load the model into VRAM before batch."""
    print(f"[INFO] warming up {model} (ctx={num_ctx}) ...", flush=True)
    t0 = time.monotonic()
    payload = json.dumps(
        {"model": model, "prompt": _WARMUP_PROMPT, "stream": False,
         "options": {"num_ctx": num_ctx}}
    ).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        print(f"[INFO] warm-up done in {time.monotonic() - t0:.0f} s", flush=True)
    except Exception as exc:
        print(f"[WARN] warm-up failed ({exc}); continuing anyway", flush=True)


def encode_image(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode()


def query_ollama(model: str, image_b64: str, url: str, prompt: str, timeout: int, num_ctx: int = 2048) -> str:
    """Query Ollama using streaming so the socket timeout resets on every token.

    With stream=False the HTTP connection is silent for the full inference
    duration.  If inference takes longer than `timeout` seconds the socket
    fires a TimeoutError even though Ollama is still working, leaving a stuck
    request in Ollama's internal queue that blocks all subsequent requests.

    With stream=True Ollama sends one JSON line per generated token.  The
    socket timeout only fires if no bytes arrive for `timeout` seconds, which
    means a genuine stall (crash/deadlock), not just slow inference.
    """
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": True,
            "options": {"temperature": 0, "num_ctx": num_ctx},
        }
    ).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    response_text = ""
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            response_text += chunk.get("response", "")
            if chunk.get("done"):
                break
    return response_text


def extract_json(text: str) -> dict | None:
    """Extract the first JSON object from text, handling surrounding prose."""
    match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def validate_values(parsed: dict) -> bool:
    """Return True when all five values are within plausible AQS ranges."""
    try:
        co2 = int(parsed["co2_ppm"])
        hcho = int(parsed["hcho_raw"])
        tvoc = int(parsed["tvoc_raw"])
        temp = int(parsed["temperature_c"])
        hum = int(parsed["humidity_percent"])
    except (KeyError, ValueError, TypeError):
        return False
    return (
        CO2_RANGE[0] <= co2 <= CO2_RANGE[1]
        and HCHO_RANGE[0] <= hcho <= HCHO_RANGE[1]
        and TVOC_RANGE[0] <= tvoc <= TVOC_RANGE[1]
        and TEMP_RANGE[0] <= temp <= TEMP_RANGE[1]
        and HUM_RANGE[0] <= hum <= HUM_RANGE[1]
    )


def assign_split(index: int, total: int, train_frac: float, val_frac: float) -> str:
    ratio = index / max(total - 1, 1)
    if ratio < train_frac:
        return "train"
    if ratio < train_frac + val_frac:
        return "validation"
    return "test"


_POST_ERROR_COOLDOWN = 30  # seconds to wait after a network error before parse retries


def ocr_image(
    image_path: Path,
    model: str,
    url: str,
    parse_retries: int,
    request_timeout: int,
    num_ctx: int = 2048,
) -> tuple[dict | None, str]:
    """Call Ollama and return (parsed_values_or_None, note).

    Retry strategy:
    - Network/timeout errors: one immediate retry (with streaming there is no
      backed-up request to drain).
    - JSON parse errors: retry up to parse_retries times.  If a network error
      occurred earlier in this call, sleep _POST_ERROR_COOLDOWN seconds before
      each parse-retry call so the model has time to finish reloading.
      Firing parse retries immediately after a crash causes each retry to hit
      a cold-reloading model that returns garbage, wasting hundreds of seconds.
    """
    image_b64 = encode_image(image_path)

    def _call() -> str:
        return query_ollama(model, image_b64, url, _PROMPT, request_timeout, num_ctx)

    had_network_error = False

    # First attempt.
    try:
        response = _call()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        had_network_error = True
        print(f"    [WARN] network error ({exc}); retrying once", flush=True)
        try:
            response = _call()
        except (urllib.error.URLError, TimeoutError, OSError) as exc2:
            return None, f"ollama_network_error: {exc2}"

    # Retry only for JSON parse failures.
    for attempt in range(1, parse_retries + 1):
        parsed = extract_json(response)
        if parsed is not None:
            break
        if attempt == parse_retries:
            return None, f"json_parse_failed after {parse_retries} attempts"
        if had_network_error:
            print(
                f"    [INFO] post-error cooldown {_POST_ERROR_COOLDOWN}s before parse retry {attempt}",
                flush=True,
            )
            time.sleep(_POST_ERROR_COOLDOWN)
        try:
            response = _call()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return None, f"ollama_network_error on parse retry: {exc}"
    else:
        return None, "json_parse_failed"

    valid_flag = str(parsed.get("valid", "false")).lower() == "true"
    plausible = validate_values(parsed)
    if not valid_flag or not plausible:
        return parsed, "ocr_invalid_or_implausible"

    return parsed, "ollama_ocr"


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    dataset_dir = args.dataset_dir.resolve()
    if not dataset_dir.is_dir():
        print(f"[ERROR] dataset-dir not found: {dataset_dir}", file=sys.stderr)
        return 1

    output_path = (args.output or dataset_dir / "labels_environment.csv").resolve()

    print(f"[INFO] dataset:  {dataset_dir}", flush=True)
    print(f"[INFO] output:   {output_path}", flush=True)
    print(f"[INFO] model:    {args.model}", flush=True)

    rows = load_manifest(dataset_dir)
    ok_rows = accepted_rows(rows, args.skip_duplicates)
    print(f"[INFO] manifest: {len(rows)} total rows, {len(ok_rows)} accepted frames", flush=True)

    existing = load_existing_labels(output_path) if args.resume else set()
    if existing:
        print(f"[INFO] resume:   skipping {len(existing)} already-labeled frames", flush=True)

    to_process = [r for r in ok_rows if r["sample_id"] not in existing]
    if args.shuffle:
        rng = random.Random(args.seed)
        rng.shuffle(to_process)
    total = len(to_process)
    if total == 0:
        print("[INFO] nothing to process", flush=True)
        return 0

    # With num_ctx=2048 all LLM layers fit on A2000 (37/37 GPU); 40s/frame typical.
    # Fall back to 120s estimate only for the default context (GPU partial offload).
    secs_per_frame = 40 if args.num_ctx <= 2048 else 120
    print(
        f"[INFO] queuing {total} frames  "
        f"(est. ~{total * secs_per_frame // 3600}h at ~{secs_per_frame}s/frame)"
        f"  timeout={args.request_timeout}s  ctx={args.num_ctx}",
        flush=True,
    )

    if args.warmup:
        warmup_model(args.model, args.ollama_url, args.request_timeout, args.num_ctx)

    # Open output in append mode so resuming works.
    write_header = not output_path.exists() or output_path.stat().st_size == 0
    out_f = output_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=OUTPUT_FIELDNAMES)
    if write_header:
        writer.writeheader()

    t_start = time.monotonic()
    succeeded = 0
    failed = 0

    for idx, row in enumerate(to_process):
        sample_id = row["sample_id"]
        img_rel = Path(row["image_path"])
        image_path = (REPO_ROOT / img_rel) if not img_rel.is_absolute() else img_rel

        if not image_path.exists():
            print(f"  [{idx + 1}/{total}] SKIP  {sample_id} — image file missing", flush=True)
            failed += 1
            continue

        split = assign_split(
            ok_rows.index(row),
            len(ok_rows),
            args.train_fraction,
            args.val_fraction,
        )

        t0 = time.monotonic()
        parsed, note = ocr_image(
            image_path, args.model, args.ollama_url, args.retries, args.request_timeout,
            args.num_ctx,
        )
        elapsed = time.monotonic() - t0

        if parsed is not None:
            valid_out = "true" if (str(parsed.get("valid", "")).lower() == "true" and note == "ollama_ocr") else "false"
            out_row = {
                "sample_id": sample_id,
                "image_path": str(img_rel),
                "temperature_c": parsed.get("temperature_c", -1),
                "humidity_percent": parsed.get("humidity_percent", -1),
                "co2_ppm": parsed.get("co2_ppm", -1),
                "hcho_raw": parsed.get("hcho_raw", -1),
                "tvoc_raw": parsed.get("tvoc_raw", -1),
                "valid": valid_out,
                "split": split,
                "notes": f"{args.lighting_label} {note}".strip() if args.lighting_label else note,
            }
            writer.writerow(out_row)
            out_f.flush()
            status = "OK   " if valid_out == "true" else "INVLD"
            succeeded += 1
        else:
            out_row = {
                "sample_id": sample_id,
                "image_path": str(img_rel),
                "temperature_c": -1,
                "humidity_percent": -1,
                "co2_ppm": -1,
                "hcho_raw": -1,
                "tvoc_raw": -1,
                "valid": "false",
                "split": split,
                "notes": note,
            }
            writer.writerow(out_row)
            out_f.flush()
            status = "FAIL "
            failed += 1

        done = idx + 1
        elapsed_total = time.monotonic() - t_start
        avg = elapsed_total / done
        remaining = avg * (total - done)
        vals = (
            f"co2={parsed.get('co2_ppm','?')} hcho={parsed.get('hcho_raw','?')} "
            f"tvoc={parsed.get('tvoc_raw','?')} t={parsed.get('temperature_c','?')} "
            f"h={parsed.get('humidity_percent','?')}"
            if parsed
            else note
        )
        print(
            f"  [{done:4d}/{total}] {status}  {sample_id}  {vals}"
            f"  ({elapsed:.1f}s  ETA {remaining / 60:.0f}min)",
            flush=True,
        )

        if args.inter_request_delay > 0 and done < total:
            time.sleep(args.inter_request_delay)

    out_f.close()
    print(
        f"[INFO] done: {succeeded} labeled, {failed} failed  →  {output_path}",
        flush=True,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
