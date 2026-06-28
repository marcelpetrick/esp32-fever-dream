from __future__ import annotations

import unittest

from tools.model_training.run_training_sweep import qualification


class QualificationTest(unittest.TestCase):
    def report(self, overall: float, digit_accuracy: float) -> dict:
        return {
            "validation_real_tflite": {
                "accuracy": overall,
                "per_digit": {
                    str(digit): {"accuracy": digit_accuracy, "total": 10, "correct": 10}
                    for digit in range(10)
                },
            }
        }

    def test_requires_overall_and_worst_digit_gates(self) -> None:
        self.assertTrue(qualification(self.report(0.99, 0.97))[0])
        self.assertFalse(qualification(self.report(0.98, 0.97))[0])
        self.assertFalse(qualification(self.report(0.99, 0.96))[0])

    def test_requires_every_digit_in_validation(self) -> None:
        report = self.report(0.99, 0.99)
        report["validation_real_tflite"]["per_digit"]["9"]["accuracy"] = None
        self.assertFalse(qualification(report)[0])


if __name__ == "__main__":
    unittest.main()
