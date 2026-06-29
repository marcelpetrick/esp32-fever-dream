#!/usr/bin/env python3
"""Audit whether a labeled capture dataset is sufficient for TinyML training."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.model_training.build_digit_dataset import locate_display  # noqa: E402

REQUIRED_DIGITS = set("0123456789")
DIGIT_RE = re.compile(r"\d")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit TinyML OCR dataset readiness.")
    parser.add_argument(
        "--labels", required=True, type=Path, help="Label CSV to audit."
    )
    parser.add_argument(
        "--json-out", required=True, type=Path, help="JSON report output."
    )
    parser.add_argument(
        "--markdown-out", required=True, type=Path, help="Markdown report output."
    )
    parser.add_argument("--min-captures", type=int, default=300)
    parser.add_argument("--min-distinct-readings", type=int, default=10)
    parser.add_argument("--min-heldout", type=int, default=50)
    parser.add_argument("--min-validation", type=int, default=50)
    parser.add_argument("--min-test", type=int, default=0,
                        help="Minimum test-split rows (0 = no test set required).")
    parser.add_argument("--min-negative", type=int, default=0,
                        help="Minimum negative/ambiguous rows (0 = none required).")
    parser.add_argument("--min-samples-per-digit", type=int, default=20)
    parser.add_argument(
        "--exempt-cross-split-batches", nargs="*", default=[],
        metavar="BATCH",
        help="Batch names that are intentionally split across train/validation "
             "(e.g. batches listed in split_within). Excluded from the "
             "capture_batches_split_exclusive check.",
    )
    parser.add_argument(
        "--max-hash-failures", type=int, default=0,
        help="Maximum number of images allowed to fail perceptual hashing "
             "(locate_display failures). 0 = zero tolerance.",
    )
    parser.add_argument(
        "--perceptual-hamming-threshold", type=int, default=2,
        help="Maximum Hamming distance between pHashes to consider two images "
             "near-duplicates. Use 0 to disable (only exact pixel-identical "
             "images flagged).",
    )
    parser.add_argument(
        "--max-missing-validation-digits", type=int, default=0,
        help="How many digit classes may be absent from the validation split "
             "before the validation_all_digits check fails. Useful when the "
             "validation set is too small to cover every sensor value.",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero when audit fails."
    )
    return parser.parse_args(list(argv))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader)


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "ok"}


def trusted_label(row: dict[str, str]) -> bool:
    """Reject model proposals unless a human explicitly approved them."""
    reviewer = row.get("reviewer", "").strip().lower()
    if reviewer.startswith("auto-") or reviewer in {"ollama", "model", "automatic"}:
        return False
    review_status = row.get("review_status", "").strip().lower()
    if review_status:
        return review_status in {"approved", "corrected", "human"}
    if "proposal_status" in row:
        return False
    return "ollama_ocr" not in row.get("notes", "").lower()


def row_label(row: dict[str, str]) -> str:
    """Build a canonical label string from whichever fields are present.

    Supports both the legacy display_text/temperature_text format and the
    current labels_environment.csv format (co2_ppm, hcho_raw, tvoc_raw,
    temperature_c, humidity_percent).  All five numeric fields contribute
    digits so the audit can count every digit position produced by
    build_digit_dataset.py.
    """
    # Legacy formats
    if row.get("display_text", "").strip():
        return row["display_text"].strip()

    # Current labels_environment.csv format
    parts: list[str] = []
    for field in ("co2_ppm", "hcho_raw", "tvoc_raw"):
        val = row.get(field, "").strip()
        if val and val != "-1":
            parts.append(f"{field}={val}")
    temp = row.get("temperature_c", "").strip()
    if temp and temp != "-1":
        parts.append(f"{temp}C")
    hum = row.get("humidity_percent", "").strip()
    if hum and hum != "-1":
        parts.append(f"{hum}%")
    if parts:
        return " ".join(parts)

    # Fallback: legacy temperature_text + humidity_percent
    return " ".join(
        part
        for part in (
            row.get("temperature_text", "").strip(),
            (
                (hum + "%")
                if hum
                else ""
            ),
        )
        if part
    )


def crop_digit_label(row: dict[str, str]) -> str:
    """Return exactly the digits emitted by build_digit_dataset.py."""
    environment_fields = (
        "co2_ppm",
        "hcho_raw",
        "tvoc_raw",
        "temperature_c",
        "humidity_percent",
    )
    if all(row.get(field, "").strip() for field in environment_fields):
        parts = [
            f"{int(row[field]):04d}"[-4:]
            for field in ("co2_ppm", "hcho_raw", "tvoc_raw")
        ]
        parts.append(f"{float(row['temperature_c']):.0f}".zfill(2)[-2:])
        parts.append(f"{int(row['humidity_percent']):02d}"[-2:])
        return "".join(parts)
    return "".join(DIGIT_RE.findall(row_label(row)))


def row_perceptual_hash(row: dict[str, str]) -> tuple[int | None, str | None]:
    image_path = Path(row.get("image_path", ""))
    if not image_path.is_absolute():
        image_path = Path.cwd() / image_path
    if not image_path.is_file():
        return None, "image_missing"
    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
    bounds = locate_display(image)
    if bounds is None:
        return None, "display_not_found"
    oriented = image.rotate(bounds.rotation) if bounds.rotation else image
    region = oriented.crop(
        (bounds.x, bounds.y, bounds.x + bounds.width, bounds.y + bounds.height)
    )
    sample = region.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(sample.get_flattened_data())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[(y * 9) + x + 1] > pixels[(y * 9) + x])
    return value, None


def evaluate(
    rows: list[dict[str, str]], labels_path: Path, args: argparse.Namespace
) -> dict[str, object]:
    candidate_rows = [
        row for row in rows if truthy(row.get("valid", "true")) and row_label(row)
    ]
    untrusted_rows = [row for row in candidate_rows if not trusted_label(row)]
    valid_rows = [row for row in candidate_rows if trusted_label(row)]
    negative_rows = [
        row
        for row in rows
        if not truthy(row.get("valid", "true")) and trusted_label(row)
    ]
    hashed_rows: list[tuple[dict[str, str], int]] = []
    hash_failures: list[str] = []
    for row in valid_rows:
        image_hash, failure = row_perceptual_hash(row)
        if failure:
            hash_failures.append(f"{row.get('sample_id', '?')}:{failure}")
        elif image_hash is not None:
            hashed_rows.append((row, image_hash))
    usable_rows = [row for row, _ in hashed_rows]
    labels = [row_label(row) for row in usable_rows]
    distinct_readings = sorted(set(labels))
    split_counts = Counter(
        row.get("split", "unassigned") or "unassigned" for row in usable_rows
    )
    digit_counts = Counter()
    split_digit_counts: dict[str, Counter[str]] = {
        "train": Counter(),
        "validation": Counter(),
        "test": Counter(),
    }
    for row in usable_rows:
        digits = crop_digit_label(row)
        digit_counts.update(digits)
        split = row.get("split", "")
        if split in split_digit_counts:
            split_digit_counts[split].update(digits)

    split_names_valid = all(
        (row.get("split", "") or "unassigned") in {"train", "validation", "test"}
        for row in valid_rows
    )
    sample_ids = [row.get("sample_id", "") for row in valid_rows]
    duplicate_sample_ids = sorted(
        sample_id for sample_id, count in Counter(sample_ids).items() if sample_id and count > 1
    )
    image_splits: dict[str, set[str]] = {}
    batch_splits: dict[str, set[str]] = {}
    for row in valid_rows:
        split = row.get("split", "") or "unassigned"
        image_path = row.get("image_path", "")
        if image_path:
            image_splits.setdefault(image_path, set()).add(split)
            batch = Path(image_path).parent.name
            batch_splits.setdefault(batch, set()).add(split)
    cross_split_images = sorted(path for path, splits in image_splits.items() if len(splits) > 1)
    exempt_batches = set(args.exempt_cross_split_batches)
    cross_split_batches = sorted(
        batch for batch, splits in batch_splits.items()
        if len(splits) > 1 and batch not in exempt_batches
    )
    hamming_threshold = args.perceptual_hamming_threshold
    cross_split_near_duplicates: list[str] = []
    if hamming_threshold > 0:
        for index, (left_row, left_hash) in enumerate(hashed_rows):
            left_split = left_row.get("split", "")
            for right_row, right_hash in hashed_rows[index + 1 :]:
                right_split = right_row.get("split", "")
                if left_split != right_split and (left_hash ^ right_hash).bit_count() <= hamming_threshold:
                    cross_split_near_duplicates.append(
                        f"{left_row.get('sample_id', '?')}:{left_split}<->"
                        f"{right_row.get('sample_id', '?')}:{right_split}"
                    )
                    if len(cross_split_near_duplicates) >= 100:
                        break
            if len(cross_split_near_duplicates) >= 100:
                break

    missing_digits = sorted(REQUIRED_DIGITS - set(digit_counts))
    underrepresented = {
        digit: digit_counts.get(digit, 0)
        for digit in sorted(REQUIRED_DIGITS)
        if digit_counts.get(digit, 0) < args.min_samples_per_digit
    }
    heldout_count = split_counts.get("validation", 0) + split_counts.get("test", 0)

    checks = {
        "minimum_captures": len(usable_rows) >= args.min_captures,
        "distinct_readings": len(distinct_readings) >= args.min_distinct_readings,
        "all_digits_present": not missing_digits,
        "samples_per_digit": not underrepresented,
        "heldout_samples": heldout_count >= args.min_heldout,
        "minimum_validation": split_counts.get("validation", 0) >= args.min_validation,
        "minimum_test": split_counts.get("test", 0) >= args.min_test,
        "minimum_negative": len(negative_rows) >= args.min_negative,
        "validation_all_digits": len(
            REQUIRED_DIGITS - set(split_digit_counts["validation"])
        ) <= args.max_missing_validation_digits,
        # Only require all digits in test split when a test split exists.
        "test_all_digits": (
            split_counts.get("test", 0) == 0
            or not (REQUIRED_DIGITS - set(split_digit_counts["test"]))
        ),
        "all_labels_trusted": not untrusted_rows,
        "split_names_valid": split_names_valid,
        "sample_ids_unique": not duplicate_sample_ids,
        "images_split_exclusive": not cross_split_images,
        "capture_batches_split_exclusive": not cross_split_batches,
        "all_images_hashable": len(hash_failures) <= args.max_hash_failures,
        "perceptual_clusters_split_exclusive": not cross_split_near_duplicates,
    }
    passed = all(checks.values())

    return {
        "tool": "model_training.audit_dataset",
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "labels_csv": str(labels_path),
        "passed": passed,
        "checks": checks,
        "requirements": {
            "min_captures": args.min_captures,
            "min_distinct_readings": args.min_distinct_readings,
            "min_heldout": args.min_heldout,
            "min_validation": args.min_validation,
            "min_test": args.min_test,
            "min_negative": args.min_negative,
            "min_samples_per_digit": args.min_samples_per_digit,
            "required_digits": "".join(sorted(REQUIRED_DIGITS)),
        },
        "summary": {
            "rows": len(rows),
            "valid_rows": len(valid_rows),
            "usable_rows": len(usable_rows),
            "untrusted_rows": len(untrusted_rows),
            "negative_rows": len(negative_rows),
            "distinct_readings": len(distinct_readings),
            "heldout_count": heldout_count,
            "split_counts": dict(sorted(split_counts.items())),
            "digit_counts": dict(sorted(digit_counts.items())),
            "split_digit_counts": {
                split: dict(sorted(counts.items()))
                for split, counts in split_digit_counts.items()
            },
            "validation_missing_digits": sorted(
                REQUIRED_DIGITS - set(split_digit_counts["validation"])
            ),
            "test_missing_digits": sorted(
                REQUIRED_DIGITS - set(split_digit_counts["test"])
            ),
            "missing_digits": missing_digits,
            "underrepresented_digits": underrepresented,
            "duplicate_sample_ids": duplicate_sample_ids,
            "cross_split_images": cross_split_images,
            "cross_split_batches": cross_split_batches,
            "hash_failure_count": len(hash_failures),
            "hash_failure_examples": hash_failures[:20],
            "cross_split_near_duplicate_count": len(cross_split_near_duplicates),
            "cross_split_near_duplicate_examples": cross_split_near_duplicates[:20],
            "sample_readings": distinct_readings[:20],
        },
        "next_actions": [
            "Capture more real images only when values have changed or lighting conditions are intentionally varied.",
            "Collect readings until every digit 0-9 appears at least 20 times.",
            "Keep at least 50 validation/test frames out of tuning.",
            "Add negative examples before trusting false-accept rates.",
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    summary = report["summary"]
    requirements = report["requirements"]
    checks = report["checks"]
    assert isinstance(summary, dict)
    assert isinstance(requirements, dict)
    assert isinstance(checks, dict)

    lines = [
        "# TinyML Dataset Audit",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Labels CSV: `{report['labels_csv']}`",
        f"Status: `{'pass' if report['passed'] else 'blocked'}`",
        "",
        "## Requirements",
        "",
        f"- Minimum valid captures: {requirements['min_captures']}",
        f"- Minimum distinct readings: {requirements['min_distinct_readings']}",
        f"- Minimum held-out validation/test captures: {requirements['min_heldout']}",
        f"- Minimum validation captures: {requirements['min_validation']}",
        f"- Minimum independent test captures: {requirements['min_test']}",
        f"- Minimum negative/ambiguous captures: {requirements['min_negative']}",
        f"- Minimum samples per digit: {requirements['min_samples_per_digit']}",
        f"- Required digits: `{requirements['required_digits']}`",
        "",
        "## Checks",
        "",
    ]
    for name, passed in checks.items():
        lines.append(f"- {name}: {'pass' if passed else 'fail'}")

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Rows: {summary['rows']}",
            f"- Valid rows: {summary['valid_rows']}",
            f"- Usable localized rows: {summary['usable_rows']}",
            f"- Untrusted rows excluded: {summary['untrusted_rows']}",
            f"- Negative/ambiguous rows: {summary['negative_rows']}",
            f"- Distinct readings: {summary['distinct_readings']}",
            f"- Held-out rows: {summary['heldout_count']}",
            f"- Splits: `{summary['split_counts']}`",
            f"- Digit counts: `{summary['digit_counts']}`",
            f"- Split digit counts: `{summary['split_digit_counts']}`",
            f"- Validation missing digits: `{summary['validation_missing_digits']}`",
            f"- Test missing digits: `{summary['test_missing_digits']}`",
            f"- Missing digits: `{summary['missing_digits']}`",
            f"- Underrepresented digits: `{summary['underrepresented_digits']}`",
            f"- Duplicate sample IDs: `{summary['duplicate_sample_ids']}`",
            f"- Cross-split images: `{summary['cross_split_images']}`",
            f"- Cross-split capture batches: `{summary['cross_split_batches']}`",
            f"- Image/hash failures: {summary['hash_failure_count']}",
            f"- Image/hash failure examples: `{summary['hash_failure_examples']}`",
            f"- Cross-split perceptual near-duplicates detected (report capped at 100): {summary['cross_split_near_duplicate_count']}",
            f"- Cross-split near-duplicate examples: `{summary['cross_split_near_duplicate_examples']}`",
            f"- Sample readings: `{summary['sample_readings']}`",
            "",
            "## Next Actions",
            "",
        ]
    )
    for action in report["next_actions"]:
        lines.append(f"- {action}")
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
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows = read_rows(args.labels)
    report = evaluate(rows, args.labels, args)
    write_report(report, args.json_out, args.markdown_out)
    if args.strict and not report["passed"]:
        print(
            f"dataset audit blocked training; see {args.markdown_out}", file=sys.stderr
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
