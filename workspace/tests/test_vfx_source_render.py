from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_source_render import prepare_render_run


class VfxSourceRenderTests(unittest.TestCase):
    def test_prepare_keeps_only_materials_used_by_each_prefab(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            source_dir.mkdir()
            prefab_a = "Assets/VFXSourceIngest/Effects/Fire.prefab"
            prefab_b = "Assets/VFXSourceIngest/Effects/Shield.prefab"
            material_a = "Assets/VFXSourceIngest/Materials/Fire.mat"
            material_b = "Assets/VFXSourceIngest/Materials/Shield.mat"
            (source_dir / "source_manifest.json").write_text(
                json.dumps(
                    {
                        "source_id": "SRC_TEST",
                        "dependencies": [
                            {"from_path": prefab_a, "to_path": material_a, "dependency_type": "material", "status": "resolved"},
                            {"from_path": prefab_b, "to_path": material_b, "dependency_type": "material", "status": "resolved"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (source_dir / "source_sample.json").write_text(
                json.dumps(
                    {
                        "sample_id": "sample_test",
                        "source_id": "SRC_TEST",
                        "extracted": {"layers": [{"source_files": [prefab_a, prefab_b]}]},
                    }
                ),
                encoding="utf-8",
            )
            (source_dir / "training_example.json").write_text(
                json.dumps(
                    {
                        "run_id": "src_test_r001",
                        "inputs": {
                            "material_selection": {
                                "texture_tag_index_status": "loaded",
                                "materials": [
                                    {"material_path": material_a, "primary_shader_path": "Shaders/Fire", "texture_bindings": [{"slot_roles": ["alpha_mask"]}]},
                                    {"material_path": material_b, "primary_shader_path": "Shaders/Shield", "texture_bindings": [{"slot_roles": ["dissolve_map"]}]},
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            paths = prepare_render_run(
                source_dir,
                root / "run",
                unity_project=root / "EffectDemo",
                time_points=[0.0, 0.2],
                resolution=(640, 360),
            )
            request = json.loads(paths["request_path"].read_text(encoding="utf-8"))
            self.assertEqual(request["run_id"], "src_test_r001")
            self.assertEqual(len(request["requests"]), 2)
            fire_spec = json.loads((root / "run" / "candidates" / "source_prefab_001_fire" / "spec.json").read_text(encoding="utf-8"))
            selection = fire_spec["layers"][0]["material_parameters"]["material_selection"]
            self.assertEqual(selection["prefab_material_count"], 1)
            self.assertEqual([item["material_path"] for item in selection["materials"]], [material_a])
            self.assertEqual(selection["materials"][0]["texture_bindings"][0]["slot_roles"], ["alpha_mask"])

    def test_prepare_rejects_unknown_prefab(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            source_dir.mkdir()
            (source_dir / "source_manifest.json").write_text('{"source_id":"SRC_TEST","dependencies":[]}', encoding="utf-8")
            (source_dir / "source_sample.json").write_text(
                '{"sample_id":"sample_test","source_id":"SRC_TEST","extracted":{"layers":[{"source_files":["Assets/One.prefab"]}]}}',
                encoding="utf-8",
            )
            (source_dir / "training_example.json").write_text('{"run_id":"src_test_r001","inputs":{"material_selection":{}}}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not in the source sample"):
                prepare_render_run(
                    source_dir,
                    root / "run",
                    unity_project=root / "EffectDemo",
                    prefab_paths=["Assets/Missing.prefab"],
                )

    def test_prepare_uses_review_case_material_and_style_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            source_dir.mkdir()
            prefab = "Assets/VFXSourceIngest/Effects/Fire.prefab"
            (source_dir / "source_manifest.json").write_text(json.dumps({"source_id": "SRC", "dependencies": []}), encoding="utf-8")
            (source_dir / "source_sample.json").write_text(json.dumps({"sample_id": "sample", "source_id": "SRC", "extracted": {"layers": [{"source_files": [prefab]}]}}), encoding="utf-8")
            (source_dir / "training_example.json").write_text(json.dumps({"run_id": "old", "inputs": {"material_selection": {}}}), encoding="utf-8")
            training_case = {
                "case_id": "fire_case",
                "prefab_path": prefab,
                "material_selection": {"material_count": 1, "materials": [{"material_path": "Assets/Fire.mat"}]},
                "target_style_profile": {"family": "cartoon"},
                "observed_style_profile": {"family": "unknown"},
            }
            prepare_render_run(
                source_dir,
                root / "run",
                unity_project=root / "EffectDemo",
                run_id="review-r001",
                training_cases=[training_case],
            )
            spec = json.loads((root / "run" / "candidates" / "source_prefab_001_fire" / "spec.json").read_text(encoding="utf-8"))

        self.assertEqual(spec["generation"]["run_id"], "review-r001")
        self.assertEqual(spec["training_case_id"], "fire_case")
        self.assertEqual(spec["target_style_profile"]["family"], "cartoon")
        self.assertEqual(spec["layers"][0]["material_parameters"]["material_selection"]["materials"][0]["material_path"], "Assets/Fire.mat")

    def test_prepare_adaptive_runtime_writes_sampling_plan_without_fixed_times(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            source_dir.mkdir()
            prefab = "Assets/VFXSourceIngest/Effects/OneSecond.prefab"
            (source_dir / "source_manifest.json").write_text(
                json.dumps(
                    {
                        "source_id": "SRC",
                        "dependencies": [
                            {
                                "from_path": prefab,
                                "to_path": "Assets/Scripts/DissolveDriver.cs",
                                "dependency_type": "script",
                                "status": "ignored",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (source_dir / "source_sample.json").write_text(json.dumps({"sample_id": "sample", "source_id": "SRC", "extracted": {"layers": [{"source_files": [prefab]}]}}), encoding="utf-8")
            (source_dir / "training_example.json").write_text(json.dumps({"run_id": "old", "inputs": {"material_selection": {}}}), encoding="utf-8")
            paths = prepare_render_run(
                source_dir,
                root / "run",
                unity_project=root / "EffectDemo",
                adaptive_runtime=True,
                target_intervals=10,
            )
            request = json.loads(paths["request_path"].read_text(encoding="utf-8"))
            spec = json.loads((root / "run" / "candidates" / "source_prefab_001_onesecond" / "spec.json").read_text(encoding="utf-8"))

        self.assertEqual(request["sampling_mode"], "adaptive_runtime")
        self.assertEqual(request["time_points_seconds"], [])
        self.assertEqual(request["sampling"]["target_intervals"], 10)
        self.assertEqual(request["sampling"]["max_interval_seconds"], 0.1)
        self.assertEqual(request["sampling"]["max_duration_seconds"], 8.0)
        self.assertTrue(request["capture_material_timeline"])
        self.assertTrue(request["requests"][0]["material_timeline_path"].endswith("material_timeline.json"))
        self.assertEqual(request["requests"][0]["source_script_fidelity"], "source_scripts_excluded")
        self.assertEqual(request["requests"][0]["ignored_script_dependency_count"], 1)
        self.assertEqual(request["requests"][0]["missing_script_count"], 0)
        self.assertEqual(spec["render_plan"]["sampling_mode"], "adaptive_runtime")
        self.assertTrue(spec["render_plan"]["material_state_capture"]["required"])
        self.assertEqual(spec["render_plan"]["material_state_capture"]["ignored_script_paths"], ["Assets/Scripts/DissolveDriver.cs"])

    def test_prepare_marks_missing_script_context_in_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            source_dir.mkdir()
            prefab = "Assets/VFXSourceIngest/Effects/MissingScript.prefab"
            (source_dir / "source_manifest.json").write_text(json.dumps({"source_id": "SRC", "dependencies": []}), encoding="utf-8")
            (source_dir / "source_sample.json").write_text(json.dumps({"sample_id": "sample", "source_id": "SRC", "extracted": {"layers": [{"source_files": [prefab]}]}}), encoding="utf-8")
            (source_dir / "training_example.json").write_text(json.dumps({"run_id": "old", "inputs": {"material_selection": {}}}), encoding="utf-8")
            paths = prepare_render_run(
                source_dir,
                root / "run",
                unity_project=root / "EffectDemo",
                adaptive_runtime=True,
                training_cases=[{"prefab_path": prefab, "runtime_observation": {"missing_script_count": 2}}],
            )
            request = json.loads(paths["request_path"].read_text(encoding="utf-8"))

        self.assertEqual(request["requests"][0]["source_script_fidelity"], "source_scripts_missing")
        self.assertEqual(request["requests"][0]["missing_script_count"], 2)


if __name__ == "__main__":
    unittest.main()
