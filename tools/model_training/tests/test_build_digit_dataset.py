from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.model_training.build_digit_dataset import read_label_rows


class TrustedInputTest(unittest.TestCase):
    def test_rejects_unreviewed_ollama_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labels.csv"
            with path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=["sample_id", "notes", "valid", "image_path"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sample_id": "capture_0001",
                        "notes": "ollama_ocr",
                        "valid": "true",
                        "image_path": "capture_0001.jpg",
                    }
                )
            with self.assertRaisesRegex(ValueError, "unreviewed automated labels"):
                read_label_rows([path])


if __name__ == "__main__":
    unittest.main()
