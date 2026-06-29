from __future__ import annotations

import unittest

from tools.model_training.verify_deployment_gate import evaluate_gate


class DeploymentGateTest(unittest.TestCase):
    def passing_model_eval(self) -> dict:
        return {
            "test_real_tflite": {
                "accuracy": 0.995,
                "per_digit": {
                    str(digit): {"accuracy": 0.98} for digit in range(10)
                },
            }
        }

    def passing_reading_eval(self) -> dict:
        return {
            "full_reading_accuracy": 0.98,
            "false_accept_rate": 0.01,
            "negative_rows": 50,
        }

    def test_passes_only_complete_release_evidence(self) -> None:
        report = evaluate_gate(
            self.passing_model_eval(),
            self.passing_reading_eval(),
            32_000,
            "kRecognitionMinConfidencePercent = 85U;",
            "recognizer without correction",
        )
        self.assertTrue(report["passed"])

    def test_current_prototype_controls_block_release(self) -> None:
        report = evaluate_gate(
            self.passing_model_eval(),
            self.passing_reading_eval(),
            32_000,
            "kRecognitionMinConfidencePercent = 30U;",
            "// Temporary mounted-prototype correction",
        )
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["confidence_threshold"])
        self.assertFalse(report["checks"]["prototype_correction_removed"])


if __name__ == "__main__":
    unittest.main()
