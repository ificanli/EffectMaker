from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.course_knowledge_adapter import build_index, export_controller_candidates


class CourseKnowledgeAdapterTests(unittest.TestCase):
    def test_indexes_verified_fact_and_excludes_unverified_assumption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "course.md"
            source.write_text(
                "# 火焰制作步骤\n"
                "教程事实：先建立核心火焰，再加入火星和烟雾。\n"
                "工程映射：使用粒子生命周期和根部亮度。状态：verified。\n"
                "# 参数猜测\n"
                "unverified_assumption：Size=5 只是待验证假设，不能当作教程事实。\n",
                encoding="utf-8",
            )
            index_paths = build_index([source], root / "index", "test_course")
            index = json.loads(index_paths["manifest"].read_text(encoding="utf-8"))
            adapter_paths = export_controller_candidates(index_paths["manifest"], root / "adapter", "test_adapter")
            adapter = json.loads(adapter_paths["manifest"].read_text(encoding="utf-8"))
            priors = [json.loads(line) for line in adapter_paths["priors"].read_text(encoding="utf-8").splitlines()]
            candidates = [json.loads(line) for line in adapter_paths["candidates"].read_text(encoding="utf-8").splitlines()]
            exclusions = [json.loads(line) for line in adapter_paths["exclusions"].read_text(encoding="utf-8").splitlines()]

        index_schema = json.loads(Path("workspace/data/vfx_generation/schemas/course_knowledge_index.schema.json").read_text(encoding="utf-8"))
        adapter_schema = json.loads(Path("workspace/data/vfx_generation/schemas/course_controller_adapter.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(index_schema).validate(index)
        Draft202012Validator(adapter_schema).validate(adapter)
        self.assertGreaterEqual(index["record_count"], 2)
        self.assertEqual(adapter["spec_prior_count"], 1)
        self.assertEqual(adapter["controller_candidate_count"], 1)
        self.assertEqual(len(priors), 1)
        self.assertEqual(priors[0]["status"], "engineering_prior_only")
        self.assertEqual(candidates[0]["training_eligibility"]["controller_sft"], False)
        self.assertTrue(any(row["reason"] == "unverified_course_evidence" for row in exclusions))

    def test_negative_verified_statement_cannot_create_verified_prior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "negative.md"
            source.write_text(
                "# 刀光复现边界\n"
                "工程映射：当前候选不能称为 verified，尚未完成 Unity 复现。\n",
                encoding="utf-8",
            )
            index_paths = build_index([source], root / "index", "negative_verified")
            index = json.loads(index_paths["manifest"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in index_paths["records"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(index["status_counts"].get("pending"), 1)
        self.assertFalse(records[0]["eligible_for_vfxspec_prior"])

    def test_negative_chinese_verified_phrase_cannot_create_verified_prior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "negative_chinese.md"
            source.write_text(
                "# 覆盖审计结论\n"
                "这份资料不是已验证的制作模板，尚未完成 Unity 复现和连续截图确认。\n",
                encoding="utf-8",
            )
            index_paths = build_index([source], root / "index", "negative_chinese")
            index = json.loads(index_paths["manifest"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in index_paths["records"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(index["status_counts"].get("pending"), 1)
        self.assertFalse(records[0]["eligible_for_vfxspec_prior"])


if __name__ == "__main__":
    unittest.main()
