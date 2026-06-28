from __future__ import annotations

import unittest

from tools.model_training.audit_dataset import row_label, trusted_label


class RowLabelLegacyTest(unittest.TestCase):
    def test_display_text_wins(self) -> None:
        row = {"display_text": "29C 43%", "temperature_text": "29C", "humidity_percent": "43"}
        self.assertEqual(row_label(row), "29C 43%")

    def test_temperature_text_humidity_fallback(self) -> None:
        row = {"temperature_text": "29C", "humidity_percent": "43"}
        self.assertIn("43", row_label(row))


class RowLabelEnvironmentTest(unittest.TestCase):
    def _row(self) -> dict[str, str]:
        return {
            "co2_ppm": "838",
            "hcho_raw": "65",
            "tvoc_raw": "82",
            "temperature_c": "28",
            "humidity_percent": "46",
        }

    def test_includes_co2(self) -> None:
        self.assertIn("838", row_label(self._row()))

    def test_includes_hcho(self) -> None:
        self.assertIn("65", row_label(self._row()))

    def test_includes_tvoc(self) -> None:
        self.assertIn("82", row_label(self._row()))

    def test_includes_temperature(self) -> None:
        self.assertIn("28", row_label(self._row()))

    def test_includes_humidity(self) -> None:
        self.assertIn("46", row_label(self._row()))

    def test_sentinel_minus_one_excluded(self) -> None:
        row = self._row()
        row["co2_ppm"] = "-1"
        label = row_label(row)
        self.assertNotIn("-1", label)
        self.assertNotIn("838", label)

    def test_different_values_give_different_labels(self) -> None:
        row_a = self._row()
        row_b = {**self._row(), "co2_ppm": "500"}
        self.assertNotEqual(row_label(row_a), row_label(row_b))

    def test_empty_row_returns_empty_string(self) -> None:
        self.assertEqual(row_label({}), "")


class TrustedLabelTest(unittest.TestCase):
    def test_legacy_human_label_is_trusted(self) -> None:
        self.assertTrue(trusted_label({"notes": "manual"}))

    def test_ollama_label_requires_review(self) -> None:
        self.assertFalse(trusted_label({"notes": "timed ollama_ocr"}))

    def test_corrected_ollama_label_is_trusted(self) -> None:
        self.assertTrue(
            trusted_label({"notes": "ollama_ocr", "review_status": "corrected"})
        )

    def test_proposal_schema_is_untrusted(self) -> None:
        self.assertFalse(trusted_label({"proposal_status": "accepted"}))


if __name__ == "__main__":
    unittest.main()
