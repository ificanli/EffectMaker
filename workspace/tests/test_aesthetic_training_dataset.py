from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.aesthetic_record_exporter import build_aesthetic_dataset
from workspace.tools.vfx_generation.aesthetic_training_dataset import build_aesthetic_training_dataset


class AestheticTrainingDatasetTests(unittest.TestCase):
    def _feedback(self, candidate_id: str, frames: list[str]) -> dict:
        return {
            "schema_version": "prefab_human_feedback.v1",
            "batch_id": "review-r001",
            "candidate_id": candidate_id,
            "reviewed_at": "2026-09-01T12:00:00Z",
            "reviewer": "local_human",
            "decision": "partial",
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
                "render_candidate_id": f"render-{candidate_id}",
                "render_paths": frames,
                "auto_eval_status": "pass",
            },
        }

    def _write_jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return path

    def _normalized_feedback(self, root: Path, candidate_id: str = "fire-001") -> Path:
        frame_a, frame_b = root / f"{candidate_id}-a.png", root / f"{candidate_id}-b.png"
        frame_a.write_bytes(b"a")
        frame_b.write_bytes(b"b")
        feedback = self._write_jsonl(root / f"{candidate_id}.jsonl", [self._feedback(candidate_id, [frame_a.name, frame_b.name])])
        return build_aesthetic_dataset([], [feedback], [], root / f"normalized-{candidate_id}", f"normalized-{candidate_id}")["records"]

    def test_missing_features_is_blocked_and_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = self._normalized_feedback(root)
            paths = build_aesthetic_training_dataset([records], [], [], root / "training", "missing_features")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines()]
            self.assertTrue(paths["aesthetic_feedback"].is_file())
            self.assertTrue(paths["preference_pairs"].is_file())

        self.assertEqual(manifest["judge_candidate_count"], 1)
        self.assertEqual(manifest["judge_training_count"], 0)
        self.assertEqual(manifest["training_gate"]["status"], "blocked_no_feature_vectors")
        self.assertTrue(any(row["reason"] == "missing_feature_vector" for row in exclusions))

    def test_matched_features_produce_judge_training_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = self._normalized_feedback(root)
            features = self._write_jsonl(root / "features.jsonl", [{
                "run_id": "review-r001",
                "candidate_id": "fire-001",
                "features": {"image.edge_density.mean": 0.4, "image.visible_ratio.max": 0.2},
            }])
            paths = build_aesthetic_training_dataset([records], [features], [], root / "training", "matched_features", minimum_judge_examples=1, minimum_preference_pairs=1)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["judge_training"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["judge_training_count"], 1)
        self.assertEqual(manifest["preference_training_count"], 0)
        self.assertEqual(manifest["training_gate"]["status"], "blocked_insufficient_labels")
        self.assertEqual(rows[0]["features"]["image.edge_density.mean"], 0.4)
        self.assertEqual(rows[0]["evaluation_group_id"], "review-r001")

    def test_same_prefab_group_stays_in_one_split(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frame_paths = []
            feedback_rows = []
            for candidate_id in ("fire-001", "fire-002"):
                frame_a, frame_b = root / f"{candidate_id}-a.png", root / f"{candidate_id}-b.png"
                frame_a.write_bytes(b"a")
                frame_b.write_bytes(b"b")
                feedback_rows.append(self._feedback(candidate_id, [frame_a.name, frame_b.name]))
                frame_paths.extend([frame_a, frame_b])
            feedback = self._write_jsonl(root / "feedback.jsonl", feedback_rows)
            records = build_aesthetic_dataset([], [feedback], [], root / "normalized", "same_group")["records"]
            features = self._write_jsonl(root / "features.jsonl", [{"run_id": "review-r001", "candidate_id": cid, "features": {"x": index}} for index, cid in enumerate(("fire-001", "fire-002"))])
            paths = build_aesthetic_training_dataset([records], [features], [], root / "training", "same_group_training")
            rows = [json.loads(line) for line in paths["judge_training"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["group_id"] for row in rows}), 1)
        self.assertEqual(len({row["split"] for row in rows}), 1)

    def test_transitive_leakage_keys_share_one_split(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = []
            for index, (candidate_id, prompt_id, prefab) in enumerate((
                ("candidate-a", "prompt-a", "Assets/FX/fire/a.prefab"),
                ("candidate-b", "prompt-a", "Assets/FX/fire/b.prefab"),
                ("candidate-c", "prompt-c", "Assets/FX/fire/b.prefab"),
            )):
                records.append({
                    "schema_version": "vfx_aesthetic_record.v1",
                    "record_id": f"record-{index}",
                    "record_kind": "observation",
                    "provenance": {
                        "source_kind": "unity_run",
                        "source_path": "workspace/data/reviews/records.jsonl",
                        "source_record_id": f"source-{index}",
                        "source_sha256": None,
                        "asset_content_sha256": None,
                        "source_group_id": None,
                        "material_group_id": None,
                        "shader_group_id": None,
                        "run_id": f"run-{index}",
                        "run_manifest_path": None,
                        "spec_path": None,
                        "prefab_path": prefab,
                        "render_candidate_id": None,
                        "timecodes": [],
                        "frame_paths": [],
                        "parent_record_ids": [],
                    },
                    "scope": {"effect_family": "fire", "style_family": "unknown", "style_keywords": [], "prompt_id": prompt_id, "candidate_ids": [candidate_id], "scene_context": []},
                    "evidence": {"visibility_status": "blocked_environment", "evidence_status": "pending", "technical_status": "not_run", "independent_visual_evidence": False, "continuous_frame_evidence": False, "visual_review_channel": "none", "evidence_notes": "观察记录。"},
                    "payload": {"observation": "观察。", "rule_candidate": None, "axes": [], "polarity": "unknown", "confidence": "unknown", "requires_unity_validation": True},
                    "training_eligibility": {"aesthetic_judge": False, "preference_training": False, "controller_sft": False, "positive_generation_supervision": False, "excluded_reasons": ["observation_only"]},
                })
            record_path = self._write_jsonl(root / "records.jsonl", records)
            paths = build_aesthetic_training_dataset([record_path], [], [], root / "training", "transitive_groups")
            assignments = [json.loads(line) for line in paths["split_assignments"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len({row["group_id"] for row in assignments}), 1)
        self.assertEqual(len({row["split"] for row in assignments}), 1)

    def test_preference_pair_requires_both_feature_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = {
                "schema_version": "vfx_aesthetic_record.v1",
                "record_id": "pair-record",
                "record_kind": "preference_pair",
                "provenance": {
                    "source_kind": "human_preference",
                    "source_path": "workspace/data/reviews/pairs.jsonl",
                    "source_record_id": "pair-001",
                    "source_sha256": None,
                    "run_id": "run-pair",
                    "run_manifest_path": "workspace/data/runs/run.json",
                    "spec_path": None,
                    "prefab_path": "Assets/FX/fire/Fx_fire.prefab",
                    "render_candidate_id": None,
                    "timecodes": [],
                    "frame_paths": ["frame-a.png", "frame-b.png", "frame-c.png", "frame-d.png"],
                    "parent_record_ids": [],
                },
                "scope": {
                    "effect_family": "fire",
                    "style_family": "cartoon",
                    "style_keywords": [],
                    "prompt_id": "prompt-fire",
                    "candidate_ids": ["candidate-a", "candidate-b"],
                    "scene_context": [],
                },
                "evidence": {
                    "visibility_status": "visible",
                    "evidence_status": "observed",
                    "technical_status": "pass",
                    "independent_visual_evidence": True,
                    "continuous_frame_evidence": True,
                    "visual_review_channel": "local_browser",
                    "evidence_notes": "人工对比。",
                },
                "payload": {
                    "candidate_a": "candidate-a",
                    "candidate_b": "candidate-b",
                    "preference": "a",
                    "comparable": True,
                    "reason_codes": ["core_readability"],
                    "human_note": "A更清楚。",
                },
                "training_eligibility": {
                    "aesthetic_judge": False,
                    "preference_training": True,
                    "controller_sft": False,
                    "positive_generation_supervision": False,
                    "excluded_reasons": [],
                },
            }
            records = self._write_jsonl(root / "records.jsonl", [record])
            features = self._write_jsonl(root / "features.jsonl", [
                {"run_id": "run-a", "candidate_id": "candidate-a", "features": {"x": 1}},
                {"run_id": "run-b", "candidate_id": "candidate-b", "features": {"x": 2}},
            ])
            paths = build_aesthetic_training_dataset([records], [features], [], root / "training", "preference_pair")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["preference_candidate_count"], 1)
        self.assertEqual(manifest["preference_training_count"], 1)
        self.assertEqual(manifest["training_gate"]["status"], "blocked_insufficient_labels")

    def test_real_r004_dataset_is_audited_without_silent_feature_assumptions(self) -> None:
        records = Path("workspace/data/vfx_generation/datasets/aesthetic_records_r004/aesthetic_records.jsonl")
        exclusions = Path("workspace/data/vfx_generation/datasets/aesthetic_records_r004/technical_exclusions.jsonl")
        self.assertTrue(records.is_file(), "real standardized aesthetic records are required")
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_aesthetic_training_dataset([records], [], [exclusions], Path(temporary) / "training", "real_r004_audit")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["judge_candidate_count"], 47)
        self.assertEqual(manifest["judge_training_count"], 0)
        self.assertEqual(manifest["preference_training_count"], 0)
        self.assertEqual(manifest["training_gate"]["status"], "blocked_no_feature_vectors")
        self.assertGreaterEqual(manifest["exclusion_counts"].get("technical_exclusion", 0), 200)


if __name__ == "__main__":
    unittest.main()
