from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.full_prefab_capture_batch import prepare_capture_batch


ROOT = Path(__file__).parents[2]


class FullPrefabCaptureBatchTests(unittest.TestCase):
    def test_real_full_baseline_selects_deterministic_diverse_playable_batch(self) -> None:
        baseline = ROOT / "workspace/data/vfx_generation/datasets/prefab_graph_full_r002"
        project = ROOT / "UnityDemo/EffectDemo"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = prepare_capture_batch(baseline, project, root / "first", "first", count=64, seed=17)
            second = prepare_capture_batch(baseline, project, root / "second", "second", count=64, seed=17)
            first_manifest = json.loads(first["manifest"].read_text(encoding="utf-8"))
            second_manifest = json.loads(second["manifest"].read_text(encoding="utf-8"))
            request = json.loads(first["request"].read_text(encoding="utf-8"))

        first_paths = [row["prefab_path"] for row in first_manifest["selected"]]
        second_paths = [row["prefab_path"] for row in second_manifest["selected"]]
        self.assertEqual(first_paths, second_paths)
        self.assertEqual(first_manifest["selected_count"], 64)
        technical = [json.loads(line) for line in (baseline / "technical_records.jsonl").read_text(encoding="utf-8").splitlines()]
        eligible_groups = {
            row["source_group"]
            for row in technical
            if row["technical_status"] == "particle_playable"
            and row["missing_script_count"] == 0
            and row["missing_material_slot_count"] == 0
            and row["missing_shader_count"] == 0
            and row["source_group"] != "VFXGenerated"
        }
        self.assertEqual(set(first_manifest["source_group_counts"]), eligible_groups)
        self.assertGreaterEqual(len(first_manifest["effect_family_counts"]), 5)
        self.assertEqual(set(first_manifest["quality_gates"].values()), {0})
        self.assertTrue(all(row["technical_status"] == "particle_playable" for row in first_manifest["selected"]))
        self.assertTrue(all(row["source_group"] != "VFXGenerated" for row in first_manifest["selected"]))
        self.assertEqual(len(request["requests"]), 64)
        self.assertEqual(request["sampling"]["max_interval_seconds"], 0.1)
        self.assertEqual(request["sampling"]["short_effect_target_intervals"], 20)
        self.assertEqual(request["sampling"]["min_interval_seconds"], 0.01)
        self.assertEqual(request["sampling"]["max_duration_seconds"], 3.0)

    def test_explicit_prefab_path_can_be_recaptured_for_framing_regression(self) -> None:
        baseline = ROOT / "workspace/data/vfx_generation/datasets/prefab_graph_full_r002"
        project = ROOT / "UnityDemo/EffectDemo"
        target = "Assets/Hovl Studio/Sword slash VFX/Prefabs/Sword Slash 1.prefab"
        with tempfile.TemporaryDirectory() as temporary:
            paths = prepare_capture_batch(
                baseline,
                project,
                Path(temporary) / "slash",
                "slash-framing",
                count=64,
                prefab_paths=[target],
                previous_manifests=[ROOT / "workspace/data/vfx_generation/captures/full_prefab_capture_r002/capture_batch_manifest.json"],
            )
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            request = json.loads(paths["request"].read_text(encoding="utf-8"))
        self.assertEqual(manifest["selection_policy"], "explicit_prefab_paths.v1")
        self.assertEqual(manifest["selected_count"], 1)
        self.assertEqual(manifest["selected"][0]["prefab_path"], target)
        self.assertEqual(request["requests"][0]["capture_category"], "slash")


if __name__ == "__main__":
    unittest.main()
