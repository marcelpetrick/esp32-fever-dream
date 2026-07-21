import unittest

from tools.model_training.run_digit_model import (
    active_co2_confidences,
    assemble_co2_text,
    optional_co2_text,
)


class Co2AssemblyTest(unittest.TestCase):
    def test_expected_co2_is_not_zero_padded(self) -> None:
        self.assertEqual(optional_co2_text({"co2_ppm": "838"}), "838")
        self.assertEqual(optional_co2_text({"co2_ppm": "1498"}), "1498")

    def test_predicted_co2_falls_back_to_three_digits_above_max(self) -> None:
        self.assertEqual(assemble_co2_text("1498"), "1498")
        self.assertEqual(assemble_co2_text("8387"), "838")

    def test_three_digit_co2_ignores_unused_fourth_confidence(self) -> None:
        self.assertEqual(active_co2_confidences("1498", [90, 91, 92, 93]), [90, 91, 92, 93])
        self.assertEqual(active_co2_confidences("8387", [90, 91, 92, 3]), [90, 91, 92])


if __name__ == "__main__":
    unittest.main()
