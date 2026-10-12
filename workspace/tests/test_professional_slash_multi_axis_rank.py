from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.professional_slash_multi_axis_rank import fuse_rankings


class ProfessionalSlashMultiAxisRankTests(unittest.TestCase):
    def test_fusion_requires_all_axes_and_uses_rank_not_raw_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = {"ranking": [{"candidate_id": "a", "score": -100.0, "distribution": {"in_distribution": True}}, {"candidate_id": "b", "score": 1000.0, "distribution": {"in_distribution": True}}]}
            second = {"ranking": [{"candidate_id": "b", "score": -3.0, "distribution": {"in_distribution": False}}, {"candidate_id": "a", "score": -4.0, "distribution": {"in_distribution": True}}]}
            (root / "first.json").write_text(json.dumps(first), encoding="utf-8")
            (root / "second.json").write_text(json.dumps(second), encoding="utf-8")
            output = fuse_rankings({"first": root / "first.json", "second": root / "second.json"}, root / "output.json")
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["all_axes_in_distribution_count"], 1)
            self.assertEqual(result["ranking"][0]["candidate_id"], "a")
            self.assertTrue(result["ranking"][0]["all_axes_in_distribution"])
            self.assertFalse(result["ranking"][1]["all_axes_in_distribution"])


if __name__ == "__main__":
    unittest.main()
