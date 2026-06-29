from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.model_training.apply_split_policy import apply_policy, load_policy


class ApplySplitPolicyTest(unittest.TestCase):
    def test_assigns_entire_capture_batch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            labels = root / "labels.csv"
            with labels.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file, fieldnames=["sample_id", "image_path", "split"]
                )
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


if __name__ == "__main__":
    unittest.main()
