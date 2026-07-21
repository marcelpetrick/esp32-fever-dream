from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from tools.model_training.evaluate_digit_crops import load_crop


class EvaluateDigitCropsTest(unittest.TestCase):
    def test_load_crop_returns_training_shape(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "crop.png"
            Image.fromarray(np.zeros((32, 24), dtype=np.uint8)).save(path)
            crop = load_crop(path)
            self.assertEqual(crop.shape, (32, 24, 1))
            self.assertEqual(float(crop.max()), 0.0)


if __name__ == "__main__":
    unittest.main()
