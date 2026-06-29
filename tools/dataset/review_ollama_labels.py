#!/usr/bin/env python3
"""Prepare Ollama proposals for review and promote reviewed ground truth."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import statistics
import sys
from pathlib import Path
from typing import Iterable

VALUE_FIELDS = (
    "co2_ppm",
    "hcho_raw",
    "tvoc_raw",
    "temperature_c",
    "humidity_percent",
)
TEMPORAL_THRESHOLDS = {
    "co2_ppm": 100,
    "hcho_raw": 10,
    "tvoc_raw": 25,
    "temperature_c": 2,
    "humidity_percent": 3,
}
REVIEW_FIELDS = [
    "review_decision",
    *(f"corrected_{field}" for field in VALUE_FIELDS),
    "reviewer",
    "reviewed_at_utc",
    "quality_reasons",
    "temporal_flags",
]
PROVENANCE_FIELDS = ["proposal_status", "model", "prompt_version"]
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
    "proposal_model",
    "prompt_version",
    "source_proposals",
]


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Create or refresh a review queue.")
    prepare.add_argument("--proposals", required=True, type=Path)
    prepare.add_argument("--audit-csv", type=Path)
    prepare.add_argument("--output", required=True, type=Path)

    promote = subparsers.add_parser("promote", help="Write reviewed ground truth.")
    promote.add_argument("--queue", required=True, type=Path)
    promote.add_argument("--output", required=True, type=Path)
    promote.add_argument(
        "--auto-approve",
        action="store_true",
        help=(
            "Stamp all accepted pending proposals as approved by 'auto-bulk-approved'. "
            "Rows with quality_reasons flags are still skipped."
        ),
    )
    return parser.parse_args(list(argv))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader.fieldnames), list(reader)


def sample_number(sample_id: str) -> int:
    match = re.search(r"(\d+)$", sample_id)
    return int(match.group(1)) if match else sys.maxsize


def temporal_flags(rows: list[dict[str, str]], neighbor_count: int = 4) -> dict[str, str]:
    accepted = [
        row
        for row in rows
        if (
            row.get("proposal_status") == "accepted"
            or (
                not row.get("proposal_status")
                and row.get("valid", "").strip().lower() == "true"
            )
        )
        and all(row.get(field, "").lstrip("-").isdigit() for field in VALUE_FIELDS)
    ]
    result: dict[str, str] = {}
    for row in accepted:
        current_number = sample_number(row["sample_id"])
        neighbors = sorted(
            (other for other in accepted if other is not row),
            key=lambda other: abs(sample_number(other["sample_id"]) - current_number),
        )[:neighbor_count]
        flags: list[str] = []
        if len(neighbors) >= 2:
            for field, threshold in TEMPORAL_THRESHOLDS.items():
                median = statistics.median(int(other[field]) for other in neighbors)
                value = int(row[field])
                if abs(value - median) > threshold:
                    flags.append(f"{field}:{value}:neighbor_median={median:g}")
        result[row["sample_id"]] = ";".join(flags)
    return result


def audit_reasons(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    _, rows = read_csv(path)
    return {
        Path(row["image_path"]).stem: row.get("rejection_reasons", "")
        for row in rows
    }


def prepare_queue(proposals_path: Path, audit_path: Path | None, output_path: Path) -> None:
    proposal_fields, proposals = read_csv(proposals_path)
    existing: dict[str, dict[str, str]] = {}
    if output_path.exists():
        _, existing_rows = read_csv(output_path)
        existing = {row["sample_id"]: row for row in existing_rows}
    flags = temporal_flags(proposals)
    quality = audit_reasons(audit_path)
    fieldnames = proposal_fields + [
        field
        for field in (*PROVENANCE_FIELDS, *REVIEW_FIELDS)
        if field not in proposal_fields
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for proposal in sorted(proposals, key=lambda row: sample_number(row["sample_id"])):
            prior = existing.get(proposal["sample_id"], {})
            output = dict(proposal)
            if not output.get("proposal_status"):
                output["proposal_status"] = (
                    "accepted"
                    if output.get("valid", "").strip().lower() == "true"
                    else "error"
                )
            output.setdefault("model", "legacy-unknown")
            output.setdefault("prompt_version", "aqs-five-field-v1")
            for field in REVIEW_FIELDS:
                output[field] = prior.get(field, "")
            output["review_decision"] = prior.get("review_decision", "pending")
            output["quality_reasons"] = quality.get(proposal["sample_id"], "")
            output["temporal_flags"] = flags.get(proposal["sample_id"], "")
            writer.writerow(output)
    temporary.replace(output_path)


def promoted_values(row: dict[str, str]) -> dict[str, int]:
    decision = row.get("review_decision", "").strip().lower()
    if decision not in {"approve", "correct"}:
        raise ValueError("row is not approved")
    values: dict[str, int] = {}
    for field in VALUE_FIELDS:
        corrected = row.get(f"corrected_{field}", "").strip()
        value = corrected if decision == "correct" and corrected else row.get(field, "")
        values[field] = int(value)
    if not 300 <= values["co2_ppm"] <= 9999:
        raise ValueError("co2_ppm outside supported range")
    if not 0 <= values["hcho_raw"] <= 999 or not 0 <= values["tvoc_raw"] <= 999:
        raise ValueError("gas value outside supported range")
    if not -10 <= values["temperature_c"] <= 60:
        raise ValueError("temperature outside supported range")
    if not 10 <= values["humidity_percent"] <= 99:
        raise ValueError("humidity must contain two display digits")
    return values


def _auto_stamp(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    stamped: list[dict[str, str]] = []
    for row in rows:
        if (
            row.get("review_decision", "").strip().lower() == "pending"
            and row.get("proposal_status") == "accepted"
        ):
            row = {**row, "review_decision": "approve", "reviewer": "owner-bulk-approved", "reviewed_at_utc": now}
        stamped.append(row)
    return stamped


def promote_queue(queue_path: Path, output_path: Path, auto_approve: bool = False) -> None:
    _, rows = read_csv(queue_path)
    if auto_approve:
        rows = _auto_stamp(rows)
    labels: list[dict[str, object]] = []
    errors: list[str] = []
    for row in rows:
        decision = row.get("review_decision", "").strip().lower()
        if decision not in {"approve", "correct"}:
            continue
        if row.get("proposal_status") != "accepted":
            errors.append(f"{row['sample_id']}: cannot promote unsuccessful proposal")
            continue
        if row.get("quality_reasons", "").strip():
            msg = f"{row['sample_id']}: image quality rejected ({row['quality_reasons']})"
            if auto_approve:
                print(f"[SKIP] {msg}", file=sys.stderr)
                continue
            errors.append(msg)
            continue
        reviewer = row.get("reviewer", "").strip()
        reviewed_at = row.get("reviewed_at_utc", "").strip()
        if not reviewer or not reviewed_at:
            errors.append(f"{row['sample_id']}: reviewer and reviewed_at_utc are required")
            continue
        try:
            values = promoted_values(row)
            dt.datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        except (ValueError, TypeError) as error:
            errors.append(f"{row['sample_id']}: {error}")
            continue
        labels.append(
            {
                "sample_id": row["sample_id"],
                "image_path": row["image_path"],
                "temperature_c": values["temperature_c"],
                "humidity_percent": values["humidity_percent"],
                "co2_ppm": values["co2_ppm"],
                "hcho_raw": values["hcho_raw"],
                "tvoc_raw": values["tvoc_raw"],
                "valid": "true",
                "split": row.get("split", ""),
                "notes": row.get("notes", ""),
                "review_status": "corrected" if decision == "correct" else "approved",
                "reviewer": reviewer,
                "reviewed_at_utc": reviewed_at,
                "proposal_model": row.get("model", ""),
                "prompt_version": row.get("prompt_version", ""),
                "source_proposals": str(queue_path),
            }
        )
    if errors:
        raise ValueError("review queue errors:\n" + "\n".join(errors))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows(labels)
    temporary.replace(output_path)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "prepare":
        prepare_queue(args.proposals, args.audit_csv, args.output)
        print(f"[INFO] wrote review queue {args.output}")
    else:
        promote_queue(args.queue, args.output, auto_approve=getattr(args, "auto_approve", False))
        print(f"[INFO] wrote reviewed labels {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
