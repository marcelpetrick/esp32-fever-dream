import unittest

from tools.dataset.auto_consensus_labels import decide


class AutoConsensusLabelsTest(unittest.TestCase):
    def proposal(self, model: str, co2: str = "838") -> dict[str, str]:
        return {
            "sample_id": "capture_0001",
            "image_path": "capture_0001.jpg",
            "temperature_c": "28",
            "humidity_percent": "46",
            "co2_ppm": co2,
            "hcho_raw": "65",
            "tvoc_raw": "179",
            "valid": "true",
            "split": "train",
            "proposal_status": "accepted",
            "model": model,
            "prompt_version": "test",
            "_source_proposals": f"{model}.csv",
        }

    def test_promotes_exact_multi_model_consensus(self) -> None:
        row = decide(
            "capture_0001",
            [self.proposal("qwen3-vl:4b"), self.proposal("llama3.2-vision:11b")],
            {},
            min_models=2,
            allow_single_model_temporal=False,
            reviewed_at="2026-07-21T00:00:00+00:00",
        )

        self.assertEqual(row["consensus_status"], "promoted")
        self.assertEqual(row["review_status"], "automated_consensus")
        self.assertEqual(row["reviewer"], "auto-consensus")

    def test_rejects_temporal_anomaly(self) -> None:
        row = decide(
            "capture_0001",
            [self.proposal("qwen3-vl:4b"), self.proposal("llama3.2-vision:11b")],
            {"temporal_flags": "co2_ppm:838:neighbor_median=1200"},
            min_models=2,
            allow_single_model_temporal=False,
            reviewed_at="2026-07-21T00:00:00+00:00",
        )

        self.assertEqual(row["consensus_status"], "excluded")
        self.assertEqual(row["consensus_reason"], "temporal_anomaly")

    def test_single_model_requires_explicit_flag(self) -> None:
        rejected = decide(
            "capture_0001",
            [self.proposal("qwen3-vl:4b")],
            {},
            min_models=2,
            allow_single_model_temporal=False,
            reviewed_at="2026-07-21T00:00:00+00:00",
        )
        promoted = decide(
            "capture_0001",
            [self.proposal("qwen3-vl:4b")],
            {},
            min_models=2,
            allow_single_model_temporal=True,
            reviewed_at="2026-07-21T00:00:00+00:00",
        )

        self.assertEqual(rejected["consensus_reason"], "insufficient_model_consensus")
        self.assertEqual(promoted["consensus_reason"], "single_model_temporal_plausible")


if __name__ == "__main__":
    unittest.main()
