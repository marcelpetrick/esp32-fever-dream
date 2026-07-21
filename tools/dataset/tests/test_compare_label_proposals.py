import unittest

from tools.dataset.compare_label_proposals import compare


class CompareLabelProposalsTest(unittest.TestCase):
    def row(self, co2: str, hcho: str, tvoc: str, status: str = "accepted") -> dict[str, str]:
        return {
            "proposal_status": status,
            "co2_ppm": co2,
            "hcho_raw": hcho,
            "tvoc_raw": tvoc,
            "temperature_c": "28",
            "humidity_percent": "46",
        }

    def test_reports_field_agreement(self) -> None:
        report = compare(
            {
                "a": self.row("838", "54", "79"),
                "b": self.row("750", "48", "37"),
                "c": self.row("574", "0", "36", status="failed"),
            },
            {
                "a": self.row("838", "54", "82"),
                "b": self.row("750", "49", "37"),
                "c": self.row("574", "0", "36"),
            },
        )

        self.assertEqual(report["common_rows"], 3)
        self.assertEqual(report["both_accepted_rows"], 2)
        self.assertEqual(report["fields"]["co2_ppm"]["exact"], 2)
        self.assertEqual(report["fields"]["hcho_raw"]["within_1"], 2)
        self.assertEqual(report["fields"]["tvoc_raw"]["within_5"], 2)


if __name__ == "__main__":
    unittest.main()
