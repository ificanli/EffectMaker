from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.vfx_controller_dataset import build_controller_dataset


class VfxControllerDatasetTests(unittest.TestCase):
    def _variation_fixture(self, root: Path, overall: str = "符合") -> tuple[Path, Path]:
        variation = root / "variation"
        candidate_id = "fixture_candidate"
        candidate_root = variation / "candidates" / candidate_id
        frames = candidate_root / "frames"
        frames.mkdir(parents=True)
        frame = frames / "frame_000_0_000.png"
        frame.write_bytes(b"fixture")
        result_path = candidate_root / "execution_result.json"
        result_path.write_text(json.dumps({
            "valid_frame_count": 1,
            "duration_seconds": 0.5,
            "frames": [{"path": "frame_000_0_000.png"}],
            "resource_audit": {"runtime_materials_live": 0, "runtime_textures_live": 0},
        }), encoding="utf-8")
        proposal_path = variation / "proposal_manifest.json"
        proposal_path.write_text(json.dumps({
            "proposal_id": candidate_id,
            "parent_candidate_id": "parent",
            "prompt_condition": {"text": "蓝色爆发", "style_family": "cartoon", "effect_families": ["explosion"]},
            "source_prefab": {"prefab_path": "Assets/FX/explosion.prefab", "effect_family_hint": "explosion", "source_category": ["battle"]},
            "material_path": "Assets/FX/explosion.mat",
            "mutation_plan": {"goal": ["blue"]},
        }), encoding="utf-8")
        variant_manifest = variation / "variant_manifest.json"
        variant_manifest.write_text(json.dumps({
            "proposal_manifest": str(proposal_path),
            "proposal_id": candidate_id,
            "execution_result_path": str(result_path),
            "technical_status": "pass",
        }), encoding="utf-8")
        overlay = root / "condition_overlay.jsonl"
        overlay.write_text(json.dumps({
            "candidate_id": candidate_id,
            "human_conditions": {"风格": "符合", "主色": "符合", "特效类别": "符合", "节奏": "符合", "无长拖尾": "符合", "整体": overall},
            "training_eligibility": {"prompt_condition_supervision": True, "positive_generation_supervision": overall == "符合"},
            "trace": {"render_paths": [str(frame)]},
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        return variant_manifest, overlay

    def _course_adapter_fixture(self, root: Path, family: str = "fire") -> Path:
        adapter = root / "course_adapter"
        adapter.mkdir(parents=True)
        candidate_path = adapter / "controller_candidates.jsonl"
        candidate_path.write_text(json.dumps({
            "schema_version": "course_controller_candidate.v1",
            "candidate_id": "course_fixture_candidate",
            "input": {
                "prompt": "课程烟花分层",
                "course_evidence": "已完成课程实验的工程映射，仅作为先验",
                "effect_family": family,
                "record_id": "course_record_001",
            },
            "target": {
                "kind": "vfxspec_prior",
                "vfxspec_path": "course_prior.json",
            },
            "provenance": {
                "knowledge_index": "course_knowledge_index.json",
                "record_id": "course_record_001",
                "source_path": "knowledge/experiments/course.md",
                "line_start": 1,
                "line_end": 4,
                "timecodes": ["00:10-00:20"],
            },
            "training_eligibility": {
                "controller_sft": False,
                "prompt_condition_supervision": False,
                "positive_generation_supervision": False,
                "preference_training": False,
                "excluded_reasons": ["course_prior_requires_unity_reproduction_and_human_confirmation"],
            },
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        (adapter / "course_knowledge_index.json").write_text("{}", encoding="utf-8")
        (adapter / "course_prior.json").write_text("{}", encoding="utf-8")
        manifest = adapter / "course_controller_adapter_manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": "course_controller_adapter.v1",
            "adapter_id": "course_fixture_adapter",
            "files": {"controller_candidates": candidate_path.name},
        }), encoding="utf-8")
        return manifest

    def test_current_variation_without_human_label_is_excluded(self) -> None:
        variation = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_variation_r009_all_layers/variant_manifest.json")
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_controller_dataset([], [variation], [], Path(temporary) / "dataset", "current_controller")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            sft_text = paths["sft"].read_text(encoding="utf-8")

        self.assertEqual(manifest["candidate_count"], 1)
        self.assertEqual(manifest["sft_example_count"], 0)
        self.assertEqual(manifest["training_gate"]["status"], "no_eligible_examples")
        self.assertFalse(sft_text.strip())

    def test_only_complete_human_positive_becomes_minimind_sft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            variation, overlay = self._variation_fixture(Path(temporary))
            paths = build_controller_dataset([], [variation], [overlay], Path(temporary) / "dataset", "positive_controller", minimum_sft_examples=1, minimum_sft_families=1)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            examples = [json.loads(line) for line in paths["examples"].read_text(encoding="utf-8").splitlines()]
            sft = [json.loads(line) for line in paths["sft"].read_text(encoding="utf-8").splitlines()]
            schema = json.loads(Path("workspace/data/vfx_generation/schemas/vfx_controller_training_example.schema.json").read_text(encoding="utf-8"))

        Draft202012Validator(schema).validate(examples[0])
        self.assertEqual(manifest["training_gate"]["status"], "ready")
        self.assertEqual(manifest["sft_example_count"], 1)
        self.assertEqual(len(sft[0]["conversations"]), 3)
        self.assertEqual(sft[0]["conversations"][-1]["role"], "assistant")

    def test_partial_overall_label_never_becomes_positive_sft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            variation, overlay = self._variation_fixture(Path(temporary), overall="部分符合")
            paths = build_controller_dataset([], [variation], [overlay], Path(temporary) / "dataset", "partial_controller")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["sft_example_count"], 0)
        self.assertEqual(manifest["training_gate"]["status"], "no_eligible_examples")
        self.assertTrue(any("overall_not_positive" in row["excluded_reasons"] for row in exclusions))

    def test_course_prior_is_audited_but_never_becomes_sft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = self._course_adapter_fixture(root)
            paths = build_controller_dataset([], [], [], root / "dataset", "course_controller", course_adapter_paths=[adapter])
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            example = json.loads(paths["examples"].read_text(encoding="utf-8").splitlines()[0])
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["course_prior_count"], 1)
        self.assertEqual(manifest["source_kind_counts"], {"course_prior": 1})
        self.assertEqual(manifest["sft_example_count"], 0)
        self.assertEqual(manifest["training_gate"]["status"], "no_eligible_examples")
        self.assertEqual(example["provenance"]["source_kind"], "course_prior")
        self.assertEqual(example["input"]["context"]["course_prior"]["status"], "engineering_prior_only")
        self.assertIn("course_prior_requires_unity_reproduction", exclusions[0]["excluded_reasons"])

    def test_excluded_course_family_does_not_count_as_sft_family_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            variation, overlay = self._variation_fixture(root, overall="符合")
            adapter = self._course_adapter_fixture(root, family="fire")
            paths = build_controller_dataset(
                [], [variation], [overlay], root / "dataset", "mixed_controller",
                course_adapter_paths=[adapter], minimum_sft_examples=1, minimum_sft_families=2,
            )
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["family_counts"], {"explosion": 1, "fire": 1})
        self.assertEqual(manifest["sft_family_counts"], {"explosion": 1})
        self.assertEqual(manifest["training_gate"]["status"], "insufficient_labels")

    def test_real_course_adapter_r003_enters_controller_audit(self) -> None:
        adapter = Path("workspace/data/vfx_generation/course_knowledge/course_controller_adapter_r003/course_controller_adapter_manifest.json")
        self.assertTrue(adapter.is_file(), "real course adapter output is required")
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_controller_dataset([], [], [], Path(temporary) / "dataset", "real_course_controller", course_adapter_paths=[adapter])
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            examples = [json.loads(line) for line in paths["examples"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["course_prior_count"], 1)
        self.assertEqual(manifest["sft_example_count"], 0)
        self.assertEqual({row["provenance"]["source_kind"] for row in examples}, {"course_prior"})
        self.assertEqual({row["input"]["context"]["course_evidence"]["status"] for row in examples}, {"prior_only"})


if __name__ == "__main__":
    unittest.main()
