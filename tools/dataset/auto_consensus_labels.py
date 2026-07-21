#!/usr/bin/env python3
"""Promote automated OCR proposals only when consensus rules pass."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.model_training.build_digit_dataset import locate_display  # noqa: E402

VALUE_FIELDS = (
    "co2_ppm",
    "hcho_raw",
    "tvoc_raw",
    "temperature_c",
    "humidity_percent",
)

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
    "consensus_status",
    "consensus_reason",
    "consensus_models",
    "consensus_votes",
]

CO2_RANGE = (300, 9999)
HCHO_RANGE = (0, 999)
TVOC_RANGE = (0, 999)
TEMP_RANGE = (-10, 60)
HUM_RANGE = (10, 99)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", action="append", required=True, type=Path)
    parser.add_argument(
        "--review-queue",
        action="append",
        type=Path,
        default=[],
        help="Optional prepared queue carrying temporal_flags and quality_reasons.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--promoted-output",
        type=Path,
        help="Optional trainable CSV containing only consensus-promoted rows.",
    )
    parser.add_argument("--report-json", required=True, type=Path)
    parser.add_argument("--report-md", required=True, type=Path)
    parser.add_argument(
        "--allow-single-model-temporal",
        action="store_true",
        help="Promote one-model rows only when temporal and quality checks pass.",
    )
    parser.add_argument("--min-models", type=int, default=2)
    parser.add_argument(
        "--require-locatable",
        action="store_true",
        help="Exclude rows whose image cannot be localized by the training display locator.",
    )
    args = parser.parse_args(list(argv))
    if args.min_models < 1:
        parser.error("--min-models must be at least 1")
    return args


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader.fieldnames), list(reader)


def accepted(row: dict[str, str]) -> bool:
    status = row.get("proposal_status", "")
    if status:
        return status == "accepted"
    return row.get("valid", "").strip().lower() == "true"


def values(row: dict[str, str]) -> tuple[int, int, int, int, int] | None:
    try:
        parsed = tuple(int(row[field]) for field in VALUE_FIELDS)
    except (KeyError, TypeError, ValueError):
        return None
    co2, hcho, tvoc, temp, hum = parsed
    if not (
        CO2_RANGE[0] <= co2 <= CO2_RANGE[1]
        and HCHO_RANGE[0] <= hcho <= HCHO_RANGE[1]
        and TVOC_RANGE[0] <= tvoc <= TVOC_RANGE[1]
        and TEMP_RANGE[0] <= temp <= TEMP_RANGE[1]
        and HUM_RANGE[0] <= hum <= HUM_RANGE[1]
    ):
        return None
    return parsed


def queue_flags(paths: list[Path]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path in paths:
        _, rows = read_csv(path)
        for row in rows:
            result[row["sample_id"]] = {
                "quality_reasons": row.get("quality_reasons", ""),
                "temporal_flags": row.get("temporal_flags", ""),
            }
    return result


def group_proposals(paths: list[Path]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in paths:
        _, rows = read_csv(path)
        for row in rows:
            copy = dict(row)
            copy["_source_proposals"] = str(path)
            grouped[copy["sample_id"]].append(copy)
    return dict(grouped)


def proposal_model(row: dict[str, str]) -> str:
    model = row.get("model", "").strip()
    source = Path(row.get("_source_proposals", "")).stem
    return model or source or "unknown"


def decide(
    sample_id: str,
    proposals: list[dict[str, str]],
    flags: dict[str, str],
    min_models: int,
    allow_single_model_temporal: bool,
    reviewed_at: str,
    require_locatable: bool = False,
    locator_cache: dict[str, str] | None = None,
) -> dict[str, str]:
    valid_votes: list[tuple[tuple[int, int, int, int, int], dict[str, str]]] = []
    for proposal in proposals:
        parsed = values(proposal)
        if accepted(proposal) and parsed is not None:
            valid_votes.append((parsed, proposal))
    if not valid_votes:
        return rejected(sample_id, proposals, "no_valid_votes", flags, reviewed_at)

    if flags.get("quality_reasons", "").strip():
        return rejected(sample_id, proposals, "quality_rejected", flags, reviewed_at)
    if flags.get("temporal_flags", "").strip():
        return rejected(sample_id, proposals, "temporal_anomaly", flags, reviewed_at)

    counts = Counter(value for value, _ in valid_votes)
    winning_values, winning_count = counts.most_common(1)[0]
    winning_rows = [row for value, row in valid_votes if value == winning_values]
    distinct_models = sorted({proposal_model(row) for row in winning_rows})

    if len(distinct_models) >= min_models:
        status = "promoted"
        reason = "multi_model_exact_consensus"
    elif allow_single_model_temporal and len(distinct_models) == 1:
        status = "promoted"
        reason = "single_model_temporal_plausible"
    else:
        return rejected(sample_id, proposals, "insufficient_model_consensus", flags, reviewed_at)

    exemplar = winning_rows[0]
    if require_locatable:
        locator_reason = locator_status(exemplar.get("image_path", ""), locator_cache)
        if locator_reason:
            return rejected(sample_id, proposals, locator_reason, flags, reviewed_at)
    co2, hcho, tvoc, temp, hum = winning_values
    return {
        "sample_id": sample_id,
        "image_path": exemplar.get("image_path", ""),
        "temperature_c": str(temp),
        "humidity_percent": str(hum),
        "co2_ppm": str(co2),
        "hcho_raw": str(hcho),
        "tvoc_raw": str(tvoc),
        "valid": "true",
        "split": exemplar.get("split", ""),
        "notes": "auto_consensus",
        "review_status": "automated_consensus",
        "reviewer": "auto-consensus",
        "reviewed_at_utc": reviewed_at,
        "proposal_model": "+".join(distinct_models),
        "prompt_version": "+".join(sorted({row.get("prompt_version", "") for row in winning_rows if row.get("prompt_version", "")})),
        "source_proposals": "+".join(sorted({row.get("_source_proposals", "") for row in winning_rows})),
        "consensus_status": status,
        "consensus_reason": reason,
        "consensus_models": "+".join(distinct_models),
        "consensus_votes": str(winning_count),
    }


def rejected(
    sample_id: str,
    proposals: list[dict[str, str]],
    reason: str,
    flags: dict[str, str],
    reviewed_at: str,
) -> dict[str, str]:
    exemplar = proposals[0] if proposals else {}
    output = {field: "" for field in LABEL_FIELDS}
    output.update(
        {
            "sample_id": sample_id,
            "image_path": exemplar.get("image_path", ""),
            "valid": "false",
            "split": exemplar.get("split", ""),
            "review_status": "excluded",
            "reviewer": "auto-consensus",
            "reviewed_at_utc": reviewed_at,
            "source_proposals": "+".join(sorted({row.get("_source_proposals", "") for row in proposals})),
            "consensus_status": "excluded",
            "consensus_reason": reason,
            "consensus_models": "+".join(sorted({proposal_model(row) for row in proposals})),
            "consensus_votes": "0",
            "notes": ";".join(part for part in [flags.get("quality_reasons", ""), flags.get("temporal_flags", "")] if part),
        }
    )
    return output


def locator_status(image_path: str, cache: dict[str, str] | None = None) -> str:
    if cache is not None and image_path in cache:
        return cache[image_path]
    path = Path(image_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    reason = ""
    try:
        with Image.open(path) as image:
            if locate_display(image) is None:
                reason = "display_not_found"
    except FileNotFoundError:
        reason = "image_missing"
    except (OSError, UnidentifiedImageError):
        reason = "image_unreadable"
    if cache is not None:
        cache[image_path] = reason
    return reason


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_report(path: Path, markdown_path: Path, rows: list[dict[str, str]]) -> None:
    reason_counts = Counter(row["consensus_reason"] for row in rows)
    status_counts = Counter(row["consensus_status"] for row in rows)
    promoted = [row for row in rows if row["consensus_status"] == "promoted"]
    report = {
        "rows": len(rows),
        "promoted_rows": len(promoted),
        "excluded_rows": len(rows) - len(promoted),
        "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Automated Consensus Label Report",
        "",
        f"- Rows: {report['rows']}",
        f"- Promoted rows: {report['promoted_rows']}",
        f"- Excluded rows: {report['excluded_rows']}",
        "",
        "## Reasons",
        "",
        "| Reason | Rows |",
        "|---|---:|",
    ]
    for reason, count in sorted(reason_counts.items()):
        lines.append(f"| {reason} | {count} |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or [])
    grouped = group_proposals(args.proposals)
    flags = queue_flags(args.review_queue)
    reviewed_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    locator_cache: dict[str, str] = {}
    rows = [
        decide(
            sample_id,
            grouped[sample_id],
            flags.get(sample_id, {}),
            args.min_models,
            args.allow_single_model_temporal,
            reviewed_at,
            args.require_locatable,
            locator_cache,
        )
        for sample_id in sorted(grouped)
    ]
    write_csv(args.output, rows)
    if args.promoted_output:
        write_csv(
            args.promoted_output,
            [row for row in rows if row["consensus_status"] == "promoted"],
        )
    write_report(args.report_json, args.report_md, rows)
    print(f"[INFO] wrote {args.output}")
    if args.promoted_output:
        print(f"[INFO] wrote {args.promoted_output}")
    print(f"[INFO] wrote {args.report_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
