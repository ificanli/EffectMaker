from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.material_trajectory_executor import (
    SMOKE_IDS,
    frame_visual_metrics,
    prepare_execution_run,
    select_spec_paths,
)


class MaterialTrajectoryExecutorTests(unittest.TestCase):
    @property
    def curriculum_root(self) -> Path:
        return Path("workspace/data/vfx_generation/curricula/material_trajectory_curriculum_r002")

    def test_smoke_selection_covers_each_category_and_real_keyword_event(self) -> None:
        selected = select_spec_paths(self.curriculum_root, "smoke")
        specs = [json.loads(path.read_text(encoding="utf-8")) for path in selected]

        self.assertEqual(tuple(path.stem for path in selected), SMOKE_IDS)
        self.assertEqual(
            {spec["category"] for spec in specs},
            {"dissolve", "flow_distortion", "emission_alpha", "mpb", "texture_swap", "keyword_material", "negative"},
        )
        keyword_spec = next(spec for spec in specs if spec["category"] == "keyword_material")
        self.assertTrue(keyword_spec["keyword_events"])
        self.assertEqual(keyword_spec["expected_signals"], ["shader_keywords_changed"])

    def test_prepare_writes_isolated_runtime_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_root = Path(temporary) / "run"
            request_path = prepare_execution_run(
                self.curriculum_root,
                run_root,
                "material_trajectory_smoke_test",
                "smoke",
                width=256,
                height=256,
                target_intervals=10,
            )
            request = json.loads(request_path.read_text(encoding="utf-8"))

            self.assertEqual(request["schema_version"], "effectdemo_material_trajectory_requests.v1")
            self.assertEqual(request["selection"]["count"], 7)
            self.assertEqual(len(request["selection"]["category_counts"]), 7)
            self.assertTrue(request["unity_project"].endswith("UnityDemo/EffectDemo"))
            self.assertEqual(request["execution_project"], request["unity_project"])
            self.assertTrue(all(Path(item["spec_path"]).is_file() for item in request["requests"]))
            self.assertTrue(all(Path(item["capture_dir"]).is_relative_to(run_root.resolve()) for item in request["requests"]))
            self.assertTrue(all(len(item["track_clamps"]) == len(json.loads(Path(item["spec_path"]).read_text(encoding="utf-8"))["parameter_tracks"]) for item in request["requests"]))
            self.assertEqual(sum(item["has_negative_mutation"] for item in request["requests"]), 1)
            self.assertTrue(request["run_resource_audit_path"].endswith("run_resource_audit.json"))

    def test_prepare_applies_context_renderer_mapping_without_touching_baseline(self) -> None:
        context_map = Path("workspace/data/vfx_generation/context_renderers/material_trajectory_context_map_r001.json")
        with tempfile.TemporaryDirectory() as temporary:
            request_path = prepare_execution_run(
                self.curriculum_root,
                Path(temporary) / "run",
                "material_trajectory_context_test",
                "full",
                trajectory_ids=["mtc_003_dissolve_mat_circlecut_2", "mtc_014_dissolve_mat_leiji_06"],
                context_map_path=context_map,
            )
            request = json.loads(request_path.read_text(encoding="utf-8"))

            mapped, baseline = request["requests"]
            self.assertEqual(request["context_renderer_count"], 1)
            self.assertTrue(mapped["prefab_path"].endswith("Fx_circlecut/eff/Fx_circlecut.prefab"))
            self.assertEqual(mapped["context_renderer_status"], "prefab_material_match")
            self.assertIsNone(baseline["prefab_path"])
            self.assertEqual(baseline["context_renderer_status"], "no_prefab_reference")

    def test_generated_no_op_negatives_only_expect_semantic_negative_signal(self) -> None:
        specs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((self.curriculum_root / "specs").glob("*.json"))]
        no_ops = [spec for spec in specs if (spec.get("negative_mutation") or {}).get("type") == "no_op"]

        self.assertTrue(no_ops)
        self.assertTrue(all(spec["expected_signals"] == ["negative_trajectory"] for spec in no_ops))

    def test_negative_mutations_match_executable_operations(self) -> None:
        specs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((self.curriculum_root / "specs").glob("*.json"))]
        negatives = [spec for spec in specs if spec.get("negative_mutation")]
        texture_negatives = [spec for spec in negatives if spec["texture_swap_events"]]
        overshoots = [spec for spec in negatives if spec["negative_mutation"]["type"] == "overshoot"]

        self.assertTrue(texture_negatives)
        self.assertTrue(all(spec["negative_mutation"]["type"] == "incompatible_texture" for spec in texture_negatives))
        self.assertTrue(all(spec["parameter_tracks"] for spec in overshoots))
        self.assertTrue(all(track["clamp_min"] is None and track["clamp_max"] is None for spec in overshoots for track in spec["parameter_tracks"]))

    def test_visual_metrics_reject_background_only_frame(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("RGB", (32, 32), (4, 5, 9)).save(root / "blank.png")
            visible = Image.new("RGB", (32, 32), (4, 5, 9))
            for x in range(10, 22):
                for y in range(10, 22):
                    visible.putpixel((x, y), (255, 255, 255))
            visible.save(root / "visible.png")

            blank_metrics = frame_visual_metrics(root, [{"path": "blank.png", "valid": True}])
            visible_metrics = frame_visual_metrics(root, [{"path": "visible.png", "valid": True}])

            self.assertEqual(blank_metrics["status"], "near_blank")
            self.assertFalse(blank_metrics["image_training_eligible"])
            self.assertEqual(visible_metrics["status"], "visible")
            self.assertTrue(visible_metrics["image_training_eligible"])


if __name__ == "__main__":
    unittest.main()
