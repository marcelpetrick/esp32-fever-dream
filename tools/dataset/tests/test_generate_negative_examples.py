import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset.generate_negative_examples import generate, parse_args


class GenerateNegativeExamplesTest(unittest.TestCase):
    def test_generates_invalid_test_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.jpg"
            Image.new("RGB", (64, 48), (120, 120, 120)).save(source)
            labels = root / "labels.csv"
            with labels.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=["sample_id", "image_path", "valid"],
                )
                writer.writeheader()
                writer.writerow({"sample_id": "source_1", "image_path": str(source), "valid": "true"})

            args = parse_args(
                [
                    "--labels",
                    str(labels),
                    "--output-dir",
                    str(root / "negatives"),
                    "--labels-out",
                    str(root / "negatives" / "labels_environment.csv"),
                    "--count",
                    "4",
                    "--seed",
                    "173",
                ]
            )

            rows = generate(args)

            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row["valid"] == "false" for row in rows))
            self.assertTrue(all(row["split"] == "test" for row in rows))
            self.assertTrue(all(Path(row["image_path"]).exists() for row in rows))


if __name__ == "__main__":
    unittest.main()
