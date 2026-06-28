from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.model_training.run_digit_model import write_summary


def result(*, accepted: bool, should_accept: bool, predicted: str = "1234") -> dict:
    return {
        "accepted": str(accepted).lower(),
        "should_accept": str(should_accept).lower(),
        "match": "true" if accepted and should_accept and predicted == "1234" else "false",
        "min_confidence_percent": 90 if accepted else 50,
        "predicted_co2_ppm": predicted,
        "expected_co2_ppm": "1234" if should_accept else "",
        "predicted_hcho_raw": predicted,
        "expected_hcho_raw": "1234" if should_accept else "",
        "predicted_tvoc_raw": predicted,
        "expected_tvoc_raw": "1234" if should_accept else "",
        "predicted_temperature_c": predicted[:2],
        "expected_temperature_c": "12" if should_accept else "",
        "predicted_humidity_percent": predicted[:2],
        "expected_humidity_percent": "12" if should_accept else "",
    }


class HonestSummaryTest(unittest.TestCase):
    def test_separates_rejection_accuracy_and_false_accepts(self) -> None:
        rows = [
            result(accepted=False, should_accept=True),
            result(accepted=True, should_accept=False),
        ]
        with TemporaryDirectory() as temp_dir:
            summary = write_summary(rows, Path(temp_dir) / "summary.json", Path("model.tflite"))
        self.assertEqual(summary["digit_accuracy"], 1.0)
        self.assertEqual(summary["full_reading_accuracy"], 0.0)
        self.assertEqual(summary["positive_rejection_rate"], 1.0)
        self.assertEqual(summary["false_accept_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
