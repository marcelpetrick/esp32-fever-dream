from __future__ import annotations

import unittest

from tools.dataset.ollama_label_batch import (
    assign_split,
    extract_json,
    validate_values,
)


class ExtractJsonTest(unittest.TestCase):
    def test_extracts_bare_json(self) -> None:
        text = '{"co2_ppm":444,"hcho_raw":13,"tvoc_raw":36,"temperature_c":27,"humidity_percent":43,"valid":true}'
        result = extract_json(text)
        assert result is not None
        self.assertEqual(result["co2_ppm"], 444)
        self.assertEqual(result["valid"], True)

    def test_extracts_json_surrounded_by_prose(self) -> None:
        text = (
            "Here is the data you asked for:\n"
            '{"co2_ppm":720,"hcho_raw":5,"tvoc_raw":12,"temperature_c":28,"humidity_percent":47,"valid":true}\n'
            "Note that values are within range."
        )
        result = extract_json(text)
        assert result is not None
        self.assertEqual(result["co2_ppm"], 720)

    def test_returns_none_on_missing_json(self) -> None:
        self.assertIsNone(extract_json("No JSON object here at all."))

    def test_returns_none_on_malformed_json(self) -> None:
        self.assertIsNone(extract_json("{co2_ppm: 444}"))


class ValidateValuesTest(unittest.TestCase):
    def _good(self) -> dict:
        return {
            "co2_ppm": 600,
            "hcho_raw": 15,
            "tvoc_raw": 40,
            "temperature_c": 25,
            "humidity_percent": 50,
        }

    def test_accepts_valid_readings(self) -> None:
        self.assertTrue(validate_values(self._good()))

    def test_rejects_co2_out_of_range(self) -> None:
        d = self._good()
        d["co2_ppm"] = 99999
        self.assertFalse(validate_values(d))

    def test_rejects_temperature_out_of_range(self) -> None:
        d = self._good()
        d["temperature_c"] = -50
        self.assertFalse(validate_values(d))

    def test_rejects_humidity_over_100(self) -> None:
        d = self._good()
        d["humidity_percent"] = 101
        self.assertFalse(validate_values(d))

    def test_rejects_missing_key(self) -> None:
        d = self._good()
        del d["tvoc_raw"]
        self.assertFalse(validate_values(d))

    def test_rejects_sentinel_minus_one(self) -> None:
        d = self._good()
        d["co2_ppm"] = -1
        self.assertFalse(validate_values(d))


class AssignSplitTest(unittest.TestCase):
    def test_first_frame_is_train(self) -> None:
        self.assertEqual(assign_split(0, 100, 0.80, 0.10), "train")

    def test_last_train_frame(self) -> None:
        self.assertEqual(assign_split(79, 100, 0.80, 0.10), "train")

    def test_first_val_frame(self) -> None:
        self.assertEqual(assign_split(80, 100, 0.80, 0.10), "validation")

    def test_last_val_frame(self) -> None:
        self.assertEqual(assign_split(89, 100, 0.80, 0.10), "validation")

    def test_test_frame(self) -> None:
        self.assertEqual(assign_split(95, 100, 0.80, 0.10), "test")

    def test_single_frame_is_train(self) -> None:
        self.assertEqual(assign_split(0, 1, 0.80, 0.10), "train")


if __name__ == "__main__":
    unittest.main()
