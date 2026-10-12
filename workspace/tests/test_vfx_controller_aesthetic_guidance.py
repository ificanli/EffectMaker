from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.vfx_controller_aesthetic_guidance import build_guidance


class ControllerAestheticGuidanceTests(unittest.TestCase):
    def test_without_models_guidance_is_safe_and_waits_for_evidence(self) -> None:
        record = build_guidance("卡通火焰爆发", "fire", "cartoon", ["高饱和"], {"source": "test"})

        self.assertEqual(record["status"], "guidance_only")
        self.assertEqual(record["evidence"]["judge"]["status"], "unavailable")
        self.assertIn("等待更多可见人工评价和偏好比较", record["mutation_plan"]["goals"])
        self.assertFalse(record["training_eligibility"]["controller_sft"])
        self.assertTrue(record["mutation_plan"]["approval_required"])

    def test_low_judge_scores_and_style_mismatch_become_traceable_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            judge = root / "judge.json"
            judge.write_text(json.dumps({
                "model_path": "models/judge.joblib",
                "predictions": [{
                    "candidate_id": "fire-001",
                    "core_readability": 1.0,
                    "layer_separation": 4.0,
                    "rhythm": 2.0,
                    "material": 1.5,
                    "composition": 4.0,
                    "quality_score": 2.0,
                    "style_family": "realistic",
                }],
            }), encoding="utf-8")
            ranking = root / "ranking.json"
            ranking.write_text(json.dumps({
                "model_path": "models/ranker.joblib",
                "ranking": [{"candidate_id": "fire-001", "preference_score": 0.91}],
            }), encoding="utf-8")
            record = build_guidance("卡通火焰爆发", "fire", "cartoon", [], {}, judge, ranking)

        self.assertIn("提高主体可读性", record["mutation_plan"]["goals"])
        self.assertIn("修复材质、贴图、流动或溶解表现", record["mutation_plan"]["goals"])
        self.assertIn("修正目标风格匹配", record["mutation_plan"]["goals"])
        self.assertIn("core_readability", record["mutation_plan"]["change"])
        self.assertEqual(record["evidence"]["preference"]["top_candidate_id"], "fire-001")

    def test_human_issue_and_next_mutation_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            feedback = root / "feedback.json"
            feedback.write_text(json.dumps({"records": [{
                "record_id": "human-001",
                "label": {"issues": ["主体不清楚"], "next_mutation": ["增加Core持续窗口"]},
            }]}, ensure_ascii=False), encoding="utf-8")
            record = build_guidance("火焰", "fire", "unknown", [], {}, feedback_paths=[feedback])

        self.assertEqual(record["evidence"]["human_feedback"]["status"], "available")
        self.assertIn("主体不清楚", record["mutation_plan"]["change"])
        self.assertIn("增加Core持续窗口", record["mutation_plan"]["change"])
        self.assertIn("human-001", record["evidence"]["human_feedback"]["record_ids"])

    def test_guidance_matches_schema_and_never_claims_training(self) -> None:
        schema = json.loads(Path("workspace/data/vfx_generation/schemas/vfx_controller_aesthetic_guidance.schema.json").read_text(encoding="utf-8"))
        record = build_guidance("蓝色能量冲击", "explosion", "cartoon", ["高饱和"], {"prefab": "Assets/FX/explosion.prefab"})

        Draft202012Validator(schema).validate(record)
        self.assertFalse(record["training_eligibility"]["controller_sft"])
        self.assertFalse(record["training_eligibility"]["preference_training"])
        self.assertFalse(record["training_eligibility"]["positive_generation_supervision"])


if __name__ == "__main__":
    unittest.main()
