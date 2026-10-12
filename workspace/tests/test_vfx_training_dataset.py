from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_training_dataset import build_prefab_training_dataset


class VfxTrainingDatasetTests(unittest.TestCase):
    def test_builds_prefab_cases_with_style_and_dependency_health(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            source_dir.mkdir()
            prefab_a = "Assets/VFXSourceIngest/Trains/Full/Battle/Fire.prefab"
            prefab_b = "Assets/VFXSourceIngest/Trains/Full/UI/Card.prefab"
            material_a = "Assets/VFXSourceIngest/Trains/Full/Materials/Fire.mat"
            material_b = "Assets/VFXSourceIngest/Trains/Full/Materials/Card.mat"
            shader = "Assets/VFXSourceIngest/Shared/Shaders/Vfx.shader"
            texture = "Assets/VFXSourceIngest/Shared/Textures/Fire.png"
            (source_dir / "source_manifest.json").write_text(
                json.dumps(
                    {
                        "source_id": "TRN_TEST",
                        "files": [{"path": prefab_a}, {"path": prefab_b}],
                        "dependencies": [
                            {"from_path": prefab_a, "to_path": material_a, "dependency_type": "material", "status": "resolved"},
                            {"from_path": prefab_b, "to_path": material_b, "dependency_type": "material", "status": "resolved"},
                            {"from_path": material_a, "to_path": shader, "dependency_type": "shader", "status": "resolved_shared"},
                            {"from_path": material_a, "to_path": texture, "dependency_type": "texture", "status": "resolved_shared"},
                            {"from_path": material_b, "to_path": None, "dependency_type": "unknown", "status": "missing"},
                            {"from_path": prefab_b, "to_path": None, "dependency_type": "script", "status": "ignored"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (source_dir / "source_sample.json").write_text(json.dumps({"source_id": "TRN_TEST"}), encoding="utf-8")
            paths = build_prefab_training_dataset(source_dir, root / "dataset")
            cases = [json.loads(line) for line in paths["prefab_cases"].read_text(encoding="utf-8").splitlines()]
            manifest = json.loads(paths["dataset_manifest"].read_text(encoding="utf-8"))
            render_queue_count = len(paths["play_mode_render_queue"].read_text(encoding="utf-8").splitlines())
            blocked_queue_count = len(paths["prefab_blocked_queue"].read_text(encoding="utf-8").splitlines())

        self.assertEqual(manifest["case_count"], 2)
        self.assertEqual(cases[0]["inputs"]["target_style_profile"]["family"], "unknown")
        self.assertEqual(cases[0]["inputs"]["material_selection"]["materials"][0]["primary_shader_path"], shader)
        self.assertEqual(cases[0]["inputs"]["material_selection"]["materials"][0]["texture_bindings"][0]["path"], texture)
        self.assertEqual(cases[1]["source"]["source_category"], ["ui"])
        self.assertEqual(cases[1]["observations"]["dependency_health"]["missing_dependency_count"], 1)
        self.assertIn("source_missing_dependency", cases[1]["training"]["blocking_reasons"])
        self.assertEqual(manifest["playability_status_counts"], {"not_audited": 2})
        self.assertEqual(manifest["play_mode_render_candidate_count"], 0)
        self.assertEqual(render_queue_count, 0)
        self.assertEqual(blocked_queue_count, 2)


if __name__ == "__main__":
    unittest.main()
