#!/usr/bin/env python3
"""Summarize capture labeling state and training readiness.

The summary is intentionally conservative: proposal files and pending review
queues are counted separately from promoted labels.  Bulk-approved reviewers are
called out because they are useful for experiment velocity but weaker evidence
than row-level human review/correction.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

CAPTURE_ROOT = Path("tools/dataset/captures")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture-root",
        type=Path,
        default=CAPTURE_ROOT,
        help="Root containing capture batch directories.",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    return parser.parse_args(list(argv) if argv is not None else None)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            return [], []
        return list(reader.fieldnames), list(reader)


def count_images(batch: Path) -> int:
    return len(list(batch.glob("*.jpg"))) + len(list(batch.glob("*.jpeg")))


def counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(
        Counter((row.get(field, "").strip() or "<blank>") for row in rows).most_common()
    )


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "ok"}


def reviewer_kind(reviewer: str) -> str:
    value = reviewer.strip().lower()
    if not value:
        return "missing"
    if value.startswith("auto-") or value in {"ollama", "model", "automatic"}:
        return "automated"
    if "bulk" in value:
        return "bulk"
    return "human"


def trusted_like_label(row: dict[str, str]) -> bool:
    """Mirror the training trust gate without importing model-training code."""
    reviewer = row.get("reviewer", "").strip().lower()
    if reviewer.startswith("auto-") or reviewer in {"ollama", "model", "automatic"}:
        return False
    review_status = row.get("review_status", "").strip().lower()
    if review_status:
        return review_status in {"approved", "corrected", "human"}
    if "proposal_status" in row:
        return False
    return "ollama_ocr" not in row.get("notes", "").lower()


def summarize_batch(batch: Path) -> dict[str, object]:
    summary: dict[str, object] = {
        "batch": batch.name,
        "images": count_images(batch),
        "has_manifest": (batch / "manifest.csv").exists(),
    }

    proposals_path = batch / "labels_ollama_proposals.csv"
    if proposals_path.exists():
        fields, rows = read_rows(proposals_path)
        summary["proposals"] = {
            "rows": len(rows),
            "status_counts": counts(rows, "proposal_status") if "proposal_status" in fields else {},
            "valid_counts": counts(rows, "valid") if "valid" in fields else {},
        }

    queue_path = batch / "labels_ollama_review_queue.csv"
    if queue_path.exists():
        fields, rows = read_rows(queue_path)
        summary["review_queue"] = {
            "rows": len(rows),
            "decision_counts": counts(rows, "review_decision") if "review_decision" in fields else {},
            "reviewer_kind_counts": dict(Counter(reviewer_kind(row.get("reviewer", "")) for row in rows)),
        }

    labels_path = batch / "labels_environment.csv"
    if labels_path.exists():
        fields, rows = read_rows(labels_path)
        reviewer_kinds = Counter(reviewer_kind(row.get("reviewer", "")) for row in rows)
        trusted_like = [
            row
            for row in rows
            if truthy(row.get("valid", "true"))
            and trusted_like_label(row)
        ]
        summary["labels"] = {
            "rows": len(rows),
            "valid_rows": sum(1 for row in rows if truthy(row.get("valid", "true"))),
            "split_counts": counts(rows, "split") if "split" in fields else {},
            "reviewer_counts": counts(rows, "reviewer") if "reviewer" in fields else {},
            "reviewer_kind_counts": dict(reviewer_kinds),
            "trusted_like_valid_rows": len(trusted_like),
        }

    return summary


def summarize(capture_root: Path) -> dict[str, object]:
    batches = [
        summarize_batch(path)
        for path in sorted(capture_root.iterdir())
        if path.is_dir()
    ]
    totals = {
        "images": sum(int(batch["images"]) for batch in batches),
        "label_rows": sum(int(batch.get("labels", {}).get("rows", 0)) for batch in batches),
        "trusted_like_valid_label_rows": sum(
            int(batch.get("labels", {}).get("trusted_like_valid_rows", 0)) for batch in batches
        ),
        "proposal_rows": sum(int(batch.get("proposals", {}).get("rows", 0)) for batch in batches),
        "review_queue_rows": sum(int(batch.get("review_queue", {}).get("rows", 0)) for batch in batches),
        "pending_review_rows": sum(
            int(batch.get("review_queue", {}).get("decision_counts", {}).get("pending", 0))
            for batch in batches
        ),
    }
    return {"capture_root": str(capture_root), "totals": totals, "batches": batches}


def render_markdown(report: dict[str, object]) -> str:
    totals = report["totals"]
    assert isinstance(totals, dict)
    lines = [
        "# Labeling Status",
        "",
        f"Capture root: `{report['capture_root']}`",
        "",
        "## Totals",
        "",
        f"- Images: {totals['images']}",
        f"- Promoted label rows: {totals['label_rows']}",
        f"- Trusted-like valid label rows: {totals['trusted_like_valid_label_rows']}",
        f"- OCR proposal rows: {totals['proposal_rows']}",
        f"- Review queue rows: {totals['review_queue_rows']}",
        f"- Pending review rows: {totals['pending_review_rows']}",
        "",
        "## Batches",
        "",
        "| Batch | Images | Labels | Trusted-like | Proposals | Pending review | Reviewer kinds |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for batch in report["batches"]:
        assert isinstance(batch, dict)
        labels = batch.get("labels", {})
        proposals = batch.get("proposals", {})
        queue = batch.get("review_queue", {})
        assert isinstance(labels, dict)
        assert isinstance(proposals, dict)
        assert isinstance(queue, dict)
        reviewer_kinds = labels.get("reviewer_kind_counts", {})
        decisions = queue.get("decision_counts", {})
        assert isinstance(reviewer_kinds, dict)
        assert isinstance(decisions, dict)
        lines.append(
            "| {batch} | {images} | {labels} | {trusted} | {proposals} | {pending} | `{reviewers}` |".format(
                batch=batch["batch"],
                images=batch["images"],
                labels=labels.get("rows", 0),
                trusted=labels.get("trusted_like_valid_rows", 0),
                proposals=proposals.get("rows", 0),
                pending=decisions.get("pending", 0),
                reviewers=dict(sorted(reviewer_kinds.items())),
            )
        )
    lines.append("")
    lines.extend(
        [
            "## Labeling rule",
            "",
            "- `labels_ollama_proposals.csv` is OCR output, not ground truth.",
            "- `labels_ollama_review_queue.csv` is the review worklist.",
            "- `labels_environment.csv` is trainable only when rows are approved/corrected with non-automated reviewer provenance.",
            "- `bulk` reviewer provenance is allowed for experiments but must be backed by spot-check reports before deployment qualification.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    report = summarize(args.capture_root)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
