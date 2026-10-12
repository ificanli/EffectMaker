from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.aesthetic_preference_review_batch import PreferenceReviewBatchError, build_preference_review_batch


class AestheticPreferenceReviewBatchTests(unittest.TestCase):
    def _write_variant(self, root: Path, index: int, *, technical: str = "pass", prompt_id: str = "prompt-1") -> Path:
        run = root / f"run-{index}"
        candidate = run / "candidate"
        frames = candidate / "frames"
        frames.mkdir(parents=True)
        frame_paths = []
        for frame_index in range(2):
            path = frames / f"frame_{frame_index}.png"
            path.write_bytes(b"frame")
            frame_paths.append({"path": path.name, "valid": True, "requested_time_seconds": frame_index / 10.0})
        result = candidate / "execution_result.json"
        result.write_text(json.dumps({"spec_path": str(run / "spec.json"), "prefab_path": "Assets/FX/fire.prefab", "valid_frame_count": 2, "frames": frame_paths}), encoding="utf-8")
        proposal = run / "proposal_manifest.json"
        proposal.write_text(json.dumps({
            "run_id": run.name,
            "proposal_id": f"proposal-{index}",
            "prompt_condition": {"prompt_id": prompt_id, "text": "卡通火焰", "style_family": "cartoon", "effect_families": ["fire"]},
            "source_prefab": {"prefab_path": "Assets/FX/fire.prefab", "effect_family_hint": "fire"},
        }, ensure_ascii=False), encoding="utf-8")
        manifest = run / "variant_manifest.json"
        manifest.write_text(json.dumps({"proposal_manifest": str(proposal), "proposal_id": f"proposal-{index}", "execution_result_path": str(result), "technical_status": technical}), encoding="utf-8")
        (run / "spec.json").write_text(json.dumps({"schema_version": "material_trajectory_spec.v1"}), encoding="utf-8")
        return manifest

    def test_builds_four_candidate_pending_ab_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifests = [self._write_variant(root, index) for index in range(4)]
            paths = build_preference_review_batch(manifests, root / "review", "preference-r001")
            batch = json.loads(paths["batch"].read_text(encoding="utf-8"))
            pairs = [json.loads(line) for line in paths["pairs"].read_text(encoding="utf-8").splitlines()]

        schema = json.loads(Path("workspace/data/vfx_generation/schemas/aesthetic_preference_review_batch.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(batch)
        self.assertEqual(batch["candidate_count"], 4)
        self.assertEqual(batch["pair_count"], 6)
        self.assertEqual(len(pairs), 6)
        self.assertTrue(all(row["preference"] is None and row["status"] == "pending" for row in pairs))

    def test_technical_fail_is_excluded_not_compared(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifests = [self._write_variant(root, index, technical="pass") for index in range(4)]
            manifests.append(self._write_variant(root, 4, technical="fail"))
            paths = build_preference_review_batch(manifests, root / "review", "preference-r002")
            batch = json.loads(paths["batch"].read_text(encoding="utf-8"))
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(batch["candidate_count"], 4)
        self.assertEqual(batch["pair_count"], 6)
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["reason"], "technical_status_not_pass")

    def test_mixed_prompt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifests = [self._write_variant(root, 0, prompt_id="prompt-a"), self._write_variant(root, 1, prompt_id="prompt-b"), self._write_variant(root, 2), self._write_variant(root, 3)]
            with self.assertRaisesRegex(PreferenceReviewBatchError, "identical prompt"):
                build_preference_review_batch(manifests, root / "review", "preference-r003")


if __name__ == "__main__":
    unittest.main()
