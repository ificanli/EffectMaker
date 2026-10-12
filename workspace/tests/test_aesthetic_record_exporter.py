from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.aesthetic_record_exporter import build_aesthetic_dataset


class AestheticRecordExporterTests(unittest.TestCase):
    def _feedback(self, candidate_id: str, frame_paths: list[str], *, decision: str = "partial", auto_eval_status: str = "pass") -> dict:
        return {
            "schema_version": "prefab_human_feedback.v1",
            "batch_id": "review-r001",
            "candidate_id": candidate_id,
            "reviewed_at": "2026-09-01T12:00:00Z",
            "reviewer": "local_human",
            "decision": decision,
            "style_family": "cartoon",
            "style_keywords": ["高饱和"],
            "quality_score": 3,
            "scores": {"core_readability": 4, "layer_separation": 3, "rhythm": 3, "material": 2, "composition": 3},
            "layer_roles": {"core": "清楚", "support": "一般", "hit": "有效", "residual": "没有"},
            "reusable_layers": ["主体"],
            "issues": ["材质普通"],
            "summary": "部分可复用",
            "confirmation_mode": "human_corrected_ai_draft",
            "trace": {
                "prefab_path": "Assets/FX/fire/Fx_fire.prefab",
                "render_candidate_id": "render-fire-001",
                "render_paths": frame_paths,
                "auto_eval_status": auto_eval_status,
            },
        }

    def _write_jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_knowledge_text_becomes_observation_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "course.md"
            source.write_text("# 火焰节奏\n主体先出现，残留慢速退出。\n", encoding="utf-8")
            paths = build_aesthetic_dataset([source], [], [], root / "dataset", "knowledge_export")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in paths["records"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["record_kind_counts"], {"observation": 1})
        self.assertEqual(manifest["judge_eligible_count"], 0)
        self.assertEqual(records[0]["evidence"]["visibility_status"], "blocked_environment")
        self.assertFalse(records[0]["training_eligibility"]["aesthetic_judge"])

    def test_visible_prefab_feedback_becomes_judge_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frame_a, frame_b = root / "frame_a.png", root / "frame_b.png"
            frame_a.write_bytes(b"frame-a")
            frame_b.write_bytes(b"frame-b")
            feedback_path = self._write_jsonl(root / "feedback.jsonl", [self._feedback("fire-001", [frame_a.name, frame_b.name])])
            paths = build_aesthetic_dataset([], [feedback_path], [], root / "dataset", "feedback_export")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in paths["judge_records"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["judge_eligible_count"], 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["scope"]["effect_family"], "fire")
        self.assertEqual(records[0]["provenance"]["prefab_path"], "Assets/FX/fire/Fx_fire.prefab")
        self.assertEqual(records[0]["provenance"]["render_candidate_id"], "render-fire-001")
        self.assertTrue(records[0]["training_eligibility"]["aesthetic_judge"])

    def test_not_visible_feedback_is_technical_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            feedback_path = self._write_jsonl(root / "feedback.jsonl", [self._feedback("fire-hidden", [], decision="not_visible", auto_eval_status="reject")])
            paths = build_aesthetic_dataset([], [feedback_path], [], root / "dataset", "hidden_export")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["judge_eligible_count"], 0)
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["record_kind"], "technical_exclusion")
        self.assertIn("technical_exclusion_is_not_aesthetic_negative", exclusions[0]["training_eligibility"]["excluded_reasons"])

    def test_prompt_condition_feedback_is_not_quality_label(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            feedback_path = self._write_jsonl(root / "prompt_feedback.jsonl", [{
                "schema_version": "prompt_condition_human_feedback.v1",
                "batch_id": "prompt-r001",
                "candidate_id": "candidate-001",
                "conditions": {"风格": "符合", "整体": "部分符合"},
                "trace": {"prefab_path": "Assets/FX/fire/Fx_fire.prefab", "render_paths": []},
            }])
            paths = build_aesthetic_dataset([], [feedback_path], [], root / "dataset", "condition_export")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["record_kind_counts"], {"observation": 1})
        self.assertEqual(manifest["judge_eligible_count"], 0)

    def test_prompt_composition_overlay_becomes_judge_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frame_a, frame_b = root / "composition_a.png", root / "composition_b.png"
            frame_a.write_bytes(b"a")
            frame_b.write_bytes(b"b")
            label = self._feedback("composition-001", [frame_a.name, frame_b.name])
            overlay_path = self._write_jsonl(root / "composition_overlay.jsonl", [{
                "schema_version": "prompt_composition_human_label_overlay.v1",
                "batch_id": "composition-r001",
                "candidate_id": "composition-001",
                "source_prefab": {"prefab_path": "Assets/FX/fire/Fx_fire.prefab"},
                "human_label": label,
                "trace": label["trace"],
            }])
            paths = build_aesthetic_dataset([], [overlay_path], [], root / "dataset", "composition_export")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["record_kind_counts"], {"human_label": 1})
        self.assertEqual(manifest["judge_eligible_count"], 1)

    def test_all_exported_records_validate_against_unified_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frame_a, frame_b = root / "a.png", root / "b.png"
            frame_a.write_bytes(b"a")
            frame_b.write_bytes(b"b")
            feedback_path = self._write_jsonl(root / "feedback.jsonl", [self._feedback("fire-001", [frame_a.name, frame_b.name])])
            exclusion_path = self._write_jsonl(root / "exclusions.jsonl", [{
                "schema_version": "prefab_training_exclusion.v1",
                "candidate_id": "hidden-001",
                "prefab_path": "Assets/FX/fire/Fx_hidden.prefab",
                "exclusion_reason": "runtime_context_required",
                "technical_status": "context_required",
            }])
            paths = build_aesthetic_dataset([], [feedback_path], [exclusion_path], root / "dataset", "schema_export")
            schema = json.loads(Path("workspace/data/vfx_generation/schemas/aesthetic_record.schema.json").read_text(encoding="utf-8"))
            validator = Draft202012Validator(schema)
            rows = [
                json.loads(line)
                for output in (paths["records"], paths["exclusions"])
                for line in output.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        for row in rows:
            validator.validate(row)
        self.assertEqual(len(rows), 2)

    def test_real_aesthetic_records_r004_has_no_unsupported_feedback_schema(self) -> None:
        root = Path("workspace/data/vfx_generation/datasets/aesthetic_records_r004")
        manifest = json.loads((root / "aesthetic_dataset_manifest.json").read_text(encoding="utf-8"))
        records = [json.loads(line) for line in (root / "aesthetic_records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        exclusions = [json.loads(line) for line in (root / "technical_exclusions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertGreater(manifest["judge_eligible_count"], 0)
        self.assertGreater(manifest["technical_exclusion_count"], 0)
        visible_labels = [row for row in records if row["record_kind"] == "human_label" and row["evidence"]["visibility_status"] == "visible"]
        self.assertGreater(len(visible_labels), 0)
        self.assertTrue(all(row["training_eligibility"]["aesthetic_judge"] for row in visible_labels))
        self.assertFalse(any(row["payload"]["exclusion_code"] == "unsupported_feedback_schema" for row in exclusions))

    def test_review_batch_metadata_overrides_ambiguous_prefab_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frame_a, frame_b = root / "a.png", root / "b.png"
            frame_a.write_bytes(b"a")
            frame_b.write_bytes(b"b")
            feedback = self._write_jsonl(root / "feedback.jsonl", [self._feedback("ambiguous-001", [frame_a.name, frame_b.name])])
            review_batch = root / "review_batch.json"
            review_batch.write_text(json.dumps({"records": [{
                "candidate_id": "ambiguous-001",
                "prefab_path": "Assets/FX/Battle/Fx_special.prefab",
                "effect_family_hint": "fire",
                "source_category": ["battle"],
            }]}, ensure_ascii=False), encoding="utf-8")
            paths = build_aesthetic_dataset([], [feedback], [], root / "dataset", "review_metadata", [review_batch])
            record = json.loads(paths["records"].read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(record["scope"]["effect_family"], "fire")
        self.assertEqual(record["scope"]["scene_context"], ["battle"])

    def test_export_writes_semantic_observation_and_feedback_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "course.md"
            source.write_text("# 火焰\n主体先出现。\n", encoding="utf-8")
            paths = build_aesthetic_dataset([source], [], [], root / "dataset", "alias_export")
            self.assertTrue(paths["reference_observations"].is_file())
            self.assertTrue(paths["aesthetic_feedback"].is_file())
            self.assertEqual(len(paths["reference_observations"].read_text(encoding="utf-8").splitlines()), 1)
            self.assertEqual(paths["aesthetic_feedback"].read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
