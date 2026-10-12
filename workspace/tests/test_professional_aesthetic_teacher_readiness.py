from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.professional_aesthetic_teacher_readiness import audit


ROOT = Path(__file__).parents[2]


class ProfessionalAestheticTeacherReadinessTests(unittest.TestCase):
    def test_current_course_index_is_audited_without_inventing_teacher_labels(self) -> None:
        source = ROOT / "workspace/data/vfx_generation/course_knowledge/course_knowledge_r003"
        with tempfile.TemporaryDirectory() as temporary:
            paths = audit(source, Path(temporary) / "teacher", "teacher-test")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            candidates = [json.loads(line) for line in paths["candidates"].read_text(encoding="utf-8").splitlines() if line.strip()]
            ready = paths["teacher_ready"].read_text(encoding="utf-8").splitlines()
        self.assertEqual(manifest["source_record_count"], 2651)
        self.assertGreater(manifest["candidate_count"], 0)
        self.assertEqual(manifest["teacher_ready_count"], 0)
        self.assertEqual(manifest["status"], "blocked_no_teacher_ready_records")
        self.assertEqual(ready, [])
        self.assertTrue(all(not row["teacher_training_eligible"] for row in candidates))
        self.assertTrue(manifest["policy"]["nonexpert_feedback_is_semantic_only"])

    def test_ready_record_preserves_executable_rule_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            record = {
                "record_id": "professional-rule-1",
                "source_path": "knowledge/source.md",
                "record_type": "tutorial_fact",
                "status": "verified",
                "effect_family": "explosion",
                "evidence_level": "high",
                "excerpt": "爆炸需要明确核心。",
                "timecodes": ["00:01:00-00:01:10"],
                "frame_paths": ["knowledge/frame.png"],
                "judgment_axes": ["core_readability"],
                "source_expertise_status": "verified_professional",
                "unity_reproduction_status": "verified",
                "unity_reproduction_report": "workspace/report.json",
            }
            (source / "course_knowledge_records.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            (source / "course_knowledge_index.json").write_text(json.dumps({
                "index_id": "test-index",
                "files": {"records": "course_knowledge_records.jsonl"},
            }), encoding="utf-8")

            paths = audit(source, root / "output", "teacher-ready-test")
            ready = json.loads(paths["teacher_ready"].read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(ready["expert_judgment"], "爆炸需要明确核心。")
        self.assertEqual(ready["judgment_axes"], ["core_readability"])
        self.assertEqual(ready["unity_reproduction_report"], "workspace/report.json")
        self.assertTrue(ready["teacher_training_eligible"])


if __name__ == "__main__":
    unittest.main()
