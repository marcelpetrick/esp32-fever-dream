from __future__ import annotations

import csv
import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.model_training.apply_split_policy import apply_policy, load_policy


class ApplySplitPolicyTest(unittest.TestCase):
    def write_labels(self, path: Path, batch: str, count: int) -> None:
        with path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=["sample_id", "image_path", "split"])
            writer.writeheader()
            for index in range(1, count + 1):
                writer.writerow(
                    {
                        "sample_id": f"capture_{index:04d}",
                        "image_path": f"captures/{batch}/capture_{index:04d}.jpg",
                        "split": "test",
                    }
                )

    def test_assigns_entire_capture_batch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            labels = root / "labels.csv"
            with labels.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["sample_id", "image_path", "split"])
                writer.writeheader()
                writer.writerow(
                    {
                        "sample_id": "capture_0001",
                        "image_path": "captures/batch_a/capture_0001.jpg",
                        "split": "test",
                    }
                )
            policy = root / "policy.json"
            policy.write_text(json.dumps({"train": ["batch_a"]}), encoding="utf-8")
            output = root / "merged.csv"
            apply_policy([labels], policy, output)
            with output.open(encoding="utf-8", newline="") as csv_file:
                row = next(csv.DictReader(csv_file))
            self.assertEqual(row["split"], "train")
            self.assertEqual(row["sample_id"], "batch_a_capture_0001")

    def test_rejects_batch_assigned_to_multiple_splits(self) -> None:
        with TemporaryDirectory() as temp_dir:
            policy = Path(temp_dir) / "policy.json"
            policy.write_text(
                json.dumps({"train": ["batch_a"], "test": ["batch_a"]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "assigned more than once"):
                load_policy(policy)

    def test_applies_interleaved_fractional_split(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            labels = root / "labels.csv"
            policy = root / "policy.json"
            output = root / "merged.csv"
            self.write_labels(labels, "long_batch", 10)
            policy.write_text(
                json.dumps(
                    {
                        "split_within": [
                            {
                                "batch": "long_batch",
                                "train": 0.6,
                                "validation": 0.2,
                                "test": 0.2,
                                "strategy": "interleaved",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            apply_policy([labels], policy, output)
            with output.open(encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))
            split_counts = Counter(row["split"] for row in rows)
            self.assertEqual(split_counts["train"], 6)
            self.assertEqual(split_counts["validation"], 2)
            self.assertEqual(split_counts["test"], 2)
            self.assertNotEqual([row["split"] for row in rows[:6]], ["train"] * 6)


if __name__ == "__main__":
    unittest.main()
