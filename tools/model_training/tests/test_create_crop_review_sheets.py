from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.model_training.create_crop_review_sheets import create_sheets


class CropReviewSheetsTest(unittest.TestCase):
    def test_groups_real_crops_by_position(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crop = root / "crop.png"
            Image.new("L", (24, 32), 128).save(crop)
            labels = root / "labels.csv"
            with labels.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=["image_path", "source", "position", "label", "split"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "image_path": crop,
                        "source": "real",
                        "position": "co2_0",
                        "label": "0",
                        "split": "train",
                    }
                )
                writer.writerow(
                    {
                        "image_path": crop,
                        "source": "synthetic",
                        "position": "synthetic_digit",
                        "label": "0",
                        "split": "train",
                    }
                )
            counts = create_sheets(labels, root / "sheets", 10)
            self.assertEqual(counts, {"co2_0": 1})
            self.assertTrue((root / "sheets" / "co2_0.png").exists())


if __name__ == "__main__":
    unittest.main()
