from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_style_review_queue import build_style_review_queue


class VfxStyleReviewQueueTests(unittest.TestCase):
    def test_splits_visible_and_rejected_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidates = []
            for candidate_id, status in (("visible", "warn"), ("blank", "reject")):
                candidate_dir = root / "candidates" / candidate_id
                candidate_dir.mkdir(parents=True)
                (candidate_dir / "spec.json").write_text(
                    json.dumps(
                        {
                            "training_case_id": f"case-{candidate_id}",
                            "layers": [{"role": "source_prefab", "shape_parameters": {"source_prefab_path": f"Assets/{candidate_id}.prefab"}}],
                        }
                    ),
                    encoding="utf-8",
                )
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "spec_path": f"candidates/{candidate_id}/spec.json",
                        "auto_eval": {"status": status, "hard_reject_reasons": ["invisible"] if status == "reject" else []},
                        "frames": [],
                    }
                )
            (root / "run_manifest.json").write_text(json.dumps({"run_id": "run", "candidates": candidates}), encoding="utf-8")
            output = build_style_review_queue(root, root / "queue.jsonl")
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(rows[0]["review_task"], "style_review")
        self.assertEqual(rows[1]["review_task"], "technical_reject_review")
        self.assertEqual(rows[1]["annotation"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
