from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.dataset.summarize_labeling_status import reviewer_kind, summarize, trusted_like_label


class LabelingStatusTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_reviewer_kind_classifies_bulk_and_automated(self) -> None:
        self.assertEqual(reviewer_kind(""), "missing")
        self.assertEqual(reviewer_kind("auto-bulk-approved"), "automated")
        self.assertEqual(reviewer_kind("owner-bulk-approved"), "bulk")
        self.assertEqual(reviewer_kind("marcel"), "human")

    def test_trusted_like_accepts_legacy_manual_labels(self) -> None:
        self.assertTrue(trusted_like_label({"notes": "manual"}))
        self.assertFalse(trusted_like_label({"notes": "ollama_ocr"}))
        self.assertFalse(
            trusted_like_label(
                {
                    "notes": "ollama_ocr",
                    "review_status": "approved",
                    "reviewer": "auto-bulk-approved",
                }
            )
        )

    def test_summarize_counts_pending_and_promoted_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch = root / "batch_a"
            batch.mkdir(parents=True)
            (batch / "capture_0001.jpg").write_bytes(b"not-an-image")
            self.write_csv(
                batch / "labels_ollama_proposals.csv",
                [
                    {
                        "sample_id": "capture_0001",
                        "valid": "true",
                        "proposal_status": "accepted",
                    }
                ],
            )
            self.write_csv(
                batch / "labels_ollama_review_queue.csv",
                [
                    {
                        "sample_id": "capture_0001",
                        "review_decision": "pending",
                        "reviewer": "",
                    }
                ],
            )
            self.write_csv(
                batch / "labels_environment.csv",
                [
                    {
                        "sample_id": "capture_0001",
                        "valid": "true",
                        "split": "train",
                        "reviewer": "owner-bulk-approved",
                    }
                ],
            )
            report = summarize(root)
            self.assertEqual(report["totals"]["images"], 1)
            self.assertEqual(report["totals"]["proposal_rows"], 1)
            self.assertEqual(report["totals"]["pending_review_rows"], 1)
            self.assertEqual(report["totals"]["trusted_like_valid_label_rows"], 1)


if __name__ == "__main__":
    unittest.main()
