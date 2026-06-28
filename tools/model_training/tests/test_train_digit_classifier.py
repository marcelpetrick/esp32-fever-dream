from __future__ import annotations

import unittest

from tools.model_training.train_digit_classifier import validate_source_splits


class SourceSplitTest(unittest.TestCase):
    def test_synthetic_validation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "synthetic rows are forbidden"):
            validate_source_splits(
                [{"source": "synthetic", "split": "validation"}]
            )

    def test_synthetic_training_and_real_heldout_are_allowed(self) -> None:
        validate_source_splits(
            [
                {"source": "synthetic", "split": "train"},
                {"source": "real", "split": "validation"},
                {"source": "real", "split": "test"},
            ]
        )


if __name__ == "__main__":
    unittest.main()
