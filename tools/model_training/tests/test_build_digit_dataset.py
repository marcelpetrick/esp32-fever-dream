from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from tools.model_training.build_digit_dataset import normalize_crop, read_label_rows


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


class FirmwarePreprocessingParityTest(unittest.TestCase):
    def test_uses_firmware_luma_minmax_and_floor_sampling(self) -> None:
        pixels = np.asarray(
            [
                [[0, 0, 0], [255, 0, 0]],
                [[0, 255, 0], [255, 255, 255]],
            ],
            dtype=np.uint8,
        )
        result = np.asarray(normalize_crop(Image.fromarray(pixels, mode="RGB")))
        self.assertEqual(result.shape, (32, 24))
        self.assertEqual(int(result[0, 0]), 0)
        self.assertEqual(int(result[0, -1]), 76)
        self.assertEqual(int(result[-1, 0]), 150)
        self.assertEqual(int(result[-1, -1]), 255)


if __name__ == "__main__":
    unittest.main()
