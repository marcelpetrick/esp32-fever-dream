from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.dataset.review_ollama_labels import (
    prepare_queue,
    promote_queue,
    temporal_flags,
)


def proposal(sample_id: str, **overrides: object) -> dict[str, str]:
    row = {
        "sample_id": sample_id,
        "image_path": f"{sample_id}.jpg",
        "temperature_c": "28",
        "humidity_percent": "46",
        "co2_ppm": "833",
        "hcho_raw": "65",
        "tvoc_raw": "178",
        "valid": "true",
        "split": "train",
        "notes": "ollama_ocr",
        "proposal_status": "accepted",
        "model": "qwen",
        "prompt_version": "v2",
    }
    row.update({key: str(value) for key, value in overrides.items()})
    return row


class TemporalFlagsTest(unittest.TestCase):
    def test_flags_known_missing_digits(self) -> None:
        rows = [proposal(f"capture_{index:04d}") for index in (11, 15, 18, 24)]
        rows.append(proposal("capture_0021", tvoc_raw=82))
        rows.append(proposal("capture_0050", humidity_percent=6))
        flags = temporal_flags(rows)
        self.assertIn("tvoc_raw", flags["capture_0021"])
        self.assertIn("humidity_percent", flags["capture_0050"])


class ReviewWorkflowTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_pending_proposals_are_not_promoted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proposals = root / "proposals.csv"
            queue = root / "queue.csv"
            labels = root / "labels.csv"
            self.write_csv(proposals, [proposal("capture_0001")])
            prepare_queue(proposals, None, queue)
            promote_queue(queue, labels)
            with labels.open(encoding="utf-8", newline="") as csv_file:
                self.assertEqual(list(csv.DictReader(csv_file)), [])

    def test_correction_is_promoted_with_provenance(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proposals = root / "proposals.csv"
            queue = root / "queue.csv"
            labels = root / "labels.csv"
            self.write_csv(proposals, [proposal("capture_0050", humidity_percent=6)])
            prepare_queue(proposals, None, queue)
            with queue.open(encoding="utf-8", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                rows = list(reader)
                assert reader.fieldnames is not None
                fields = reader.fieldnames
            rows[0]["review_decision"] = "correct"
            rows[0]["corrected_humidity_percent"] = "46"
            rows[0]["reviewer"] = "human"
            rows[0]["reviewed_at_utc"] = "2026-06-29T00:00:00Z"
            with queue.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            promote_queue(queue, labels)
            with labels.open(encoding="utf-8", newline="") as csv_file:
                promoted = list(csv.DictReader(csv_file))
            self.assertEqual(promoted[0]["humidity_percent"], "46")
            self.assertEqual(promoted[0]["review_status"], "corrected")

    def test_quality_rejected_row_cannot_be_promoted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = root / "queue.csv"
            labels = root / "labels.csv"
            row = proposal("capture_0050")
            row.update(
                {
                    "review_decision": "approve",
                    "reviewer": "human",
                    "reviewed_at_utc": "2026-06-29T00:00:00Z",
                    "quality_reasons": "display_not_found",
                }
            )
            self.write_csv(queue, [row])
            with self.assertRaisesRegex(ValueError, "image quality rejected"):
                promote_queue(queue, labels)

    def test_auto_approve_promotes_clean_pending_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proposals = root / "proposals.csv"
            queue = root / "queue.csv"
            labels = root / "labels.csv"
            self.write_csv(proposals, [proposal("capture_0001")])
            prepare_queue(proposals, None, queue)
            promote_queue(queue, labels, auto_approve=True)
            with labels.open(encoding="utf-8", newline="") as csv_file:
                promoted = list(csv.DictReader(csv_file))
            self.assertEqual(len(promoted), 1)
            self.assertEqual(promoted[0]["reviewer"], "auto-bulk-approved")
            self.assertEqual(promoted[0]["review_status"], "approved")

    def test_auto_approve_skips_quality_flagged_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = root / "queue.csv"
            labels = root / "labels.csv"
            clean = {**proposal("capture_0001"), "quality_reasons": "", "review_decision": "pending"}
            flagged = {**proposal("capture_0002"), "quality_reasons": "display_not_found", "review_decision": "pending"}
            self.write_csv(queue, [clean, flagged])
            promote_queue(queue, labels, auto_approve=True)
            with labels.open(encoding="utf-8", newline="") as csv_file:
                promoted = list(csv.DictReader(csv_file))
            promoted_ids = {r["sample_id"] for r in promoted}
            self.assertIn("capture_0001", promoted_ids)
            self.assertNotIn("capture_0002", promoted_ids)


if __name__ == "__main__":
    unittest.main()
