from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from tools.dataset import audit_capture_corpus as audit
from tools.model_training.build_digit_dataset import DisplayBounds


class AuditCaptureCorpusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bounds = DisplayBounds(80, 60, 480, 360, 0, 1000)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_noise_jpeg(self, path: Path, size: tuple[int, int] = (640, 480), seed: int = 7) -> None:
        pixels = np.random.default_rng(seed).integers(20, 230, (size[1], size[0], 3), dtype=np.uint8)
        Image.fromarray(pixels, mode="RGB").save(path, format="JPEG", quality=90)

    @patch.object(audit, "locate_display")
    def test_emits_csv_json_and_rejects_near_duplicate(self, locator) -> None:
        locator.return_value = self.bounds
        first = self.root / "first.jpg"
        second = self.root / "second.jpg"
        self.write_noise_jpeg(first)
        second.write_bytes(first.read_bytes())
        output = self.root / "report"

        result = audit.main([str(self.root), "--output-dir", str(output), "--strict", "--min-accepted", "1"])

        self.assertEqual(result, 0)
        with (output / "capture_corpus_audit.csv").open(newline="", encoding="utf-8") as csv_file:
            rows = list(csv.DictReader(csv_file))
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["accepted"] for row in rows], ["True", "False"])
        self.assertEqual(rows[1]["rejection_reasons"], "near_duplicate")
        self.assertEqual(rows[1]["nearest_hash_distance"], "0")
        report = json.loads((output / "capture_corpus_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(report["counts"], {"accepted": 1, "rejected": 1, "scanned": 2})

    @patch.object(audit, "locate_display")
    def test_strict_fails_for_wrong_dimensions_and_corrupt_jpeg(self, locator) -> None:
        locator.return_value = self.bounds
        self.write_noise_jpeg(self.root / "wrong.jpg", size=(320, 240))
        (self.root / "broken.jpg").write_bytes(b"not a jpeg")
        output = self.root / "report"

        result = audit.main([str(self.root), "--output-dir", str(output), "--strict", "--min-accepted", "1"])

        self.assertEqual(result, 2)
        with (output / "capture_corpus_audit.csv").open(newline="", encoding="utf-8") as csv_file:
            rows = {Path(row["image_path"]).name: row for row in csv.DictReader(csv_file)}
        self.assertIn("invalid_dimensions", rows["wrong.jpg"]["rejection_reasons"])
        self.assertTrue(rows["broken.jpg"]["rejection_reasons"].startswith("decode_error:"))

    @patch.object(audit, "locate_display")
    def test_explicit_non_jpeg_is_audited(self, locator) -> None:
        locator.return_value = self.bounds
        image_path = self.root / "capture.png"
        pixels = np.random.default_rng(11).integers(20, 230, (480, 640, 3), dtype=np.uint8)
        Image.fromarray(pixels, mode="RGB").save(image_path, format="PNG")
        output = self.root / "report"

        result = audit.main([str(image_path), "--output-dir", str(output)])

        self.assertEqual(result, 0)
        with (output / "capture_corpus_audit.csv").open(newline="", encoding="utf-8") as csv_file:
            row = next(csv.DictReader(csv_file))
        self.assertEqual(row["jpeg_format"], "False")
        self.assertEqual(row["rejection_reasons"], "not_jpeg")


if __name__ == "__main__":
    unittest.main()
