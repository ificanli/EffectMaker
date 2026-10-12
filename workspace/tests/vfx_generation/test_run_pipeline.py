from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from workspace.tools import unity_capture
from workspace.tools.vfx_generation.run_pipeline import build_run_outputs


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), color).save(path)


class VfxRunPipelineTests(unittest.TestCase):
    def _make_project(self, root: Path) -> Path:
        project = root / "UnityProject"
        (project / "Assets").mkdir(parents=True)
        (project / "ProjectSettings").mkdir()
        (project / "Packages").mkdir()
        _write_text(project / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 6000.5.9f1\n")
        _write_text(project / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))
        return project

    def _make_candidate(
        self,
        candidate_dir: Path,
        *,
        candidate_id: str,
        seed: int,
        scene: str,
        camera: str,
        render_time_points: list[float],
        colors: list[tuple[int, int, int]],
        with_material_timeline: bool = False,
    ) -> None:
        capture_root = candidate_dir / "captures"
        frames = []
        for index, (time_point, color) in enumerate(zip(render_time_points, colors)):
            frame_path = capture_root / f"frame_{index:04d}.png"
            _write_image(frame_path, color)
            frames.append(
                {
                    "requested_time_seconds": time_point,
                    "path": frame_path.relative_to(capture_root).as_posix(),
                }
            )
        unity_capture.write_manifest(
            candidate_dir / "capture_manifest.json",
            root=capture_root,
            scene=scene,
            effect=candidate_id,
            camera=camera,
            resolution=(32, 32),
            editor_status="ready",
            play_requested=True,
            frames=frames,
        )
        if with_material_timeline:
            timeline_path = candidate_dir / "material_timeline.json"
            _write_text(
                timeline_path,
                json.dumps(
                    {
                        "schema_version": "vfx_material_timeline.v1",
                        "source_script_fidelity": "no_ignored_script_dependencies",
                        "ignored_script_dependency_count": 0,
                        "summary": {
                            "frame_count": 2,
                            "delta_count": 1,
                            "changed_frame_count": 1,
                            "has_dynamic_material_state": True,
                            "key_material_change_times": [0.5],
                        },
                        "frames": [],
                    }
                ),
            )
            capture_manifest_path = candidate_dir / "capture_manifest.json"
            capture_manifest = json.loads(capture_manifest_path.read_text(encoding="utf-8"))
            capture_manifest["material_timeline_path"] = timeline_path.as_posix()
            for index, frame in enumerate(capture_manifest["frames"]):
                frame["material_timeline_frame_index"] = index
            _write_text(capture_manifest_path, json.dumps(capture_manifest))
        _write_text(
            candidate_dir / "spec.json",
            json.dumps(
                {
                    "schema_version": "vfxspec.v1",
                    "effect_family": "slash",
                    "effect_type": "slash",
                    "generation": {
                        "run_id": "slash_arc_pref_001_r001",
                        "candidate_id": candidate_id,
                        "seed": seed,
                        "generator": "test.generator",
                        "generator_version": "1.0.0",
                        "parent_candidate_id": None,
                    },
                    "render_plan": {
                        "unity_project": "UnityProject",
                        "scene": scene,
                        "camera": camera,
                        "resolution": [32, 32],
                        "time_points_seconds": render_time_points,
                    },
                    "layers": [{"role": "core_blade", "status": "active"}],
                },
                ensure_ascii=False,
            ),
        )

    def test_build_run_outputs_writes_manifest_auto_eval_and_contact_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._make_project(root)
            run_root = root / "runs" / "slash_arc_pref_001_r001"
            prompt_path = root / "prompts" / "slash_arc_001.md"
            _write_text(prompt_path, "# prompt\n")

            self._make_candidate(
                run_root / "candidates" / "cand-a",
                candidate_id="cand-a",
                seed=11,
                scene="SlashComparison",
                camera="Main Camera",
                render_time_points=[0.3, 0.5],
                colors=[(40, 10, 10), (80, 20, 20)],
                with_material_timeline=True,
            )
            self._make_candidate(
                run_root / "candidates" / "cand-b",
                candidate_id="cand-b",
                seed=22,
                scene="OtherScene",
                camera="Main Camera",
                render_time_points=[0.3, 0.5],
                colors=[(10, 60, 120), (10, 120, 180)],
            )

            paths = build_run_outputs(
                run_root,
                prompt_path=prompt_path,
                unity_project=project,
                scene="SlashComparison",
                camera="Main Camera",
                resolution=(32, 32),
                render_time_points_seconds=[0.3, 0.5],
                page_size=1,
            )

            manifest = json.loads((paths["run_manifest"]).read_text(encoding="utf-8"))
            auto_eval_lines = [
                json.loads(line)
                for line in (paths["auto_eval"]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            page_paths = [run_root / path for path in manifest["contact_sheet_paths"]]

            self.assertEqual(manifest["schema_version"], "vfx_run_manifest.v1")
            self.assertEqual(manifest["run_id"], "slash_arc_pref_001_r001")
            self.assertEqual(manifest["candidate_count"], 2)
            self.assertEqual(manifest["candidate_status_counts"]["pass"], 1)
            self.assertEqual(manifest["candidate_status_counts"]["reject"], 1)
            self.assertEqual(manifest["candidate_root_path"], "candidates")
            self.assertEqual(manifest["material_state_summary"], {"ready_timeline_count": 1, "dynamic_candidate_count": 1, "delta_count": 1})
            self.assertEqual(manifest["render_time_points_seconds"], [0.3, 0.5])
            self.assertEqual(len(manifest["contact_sheet_paths"]), 2)
            self.assertTrue((paths["feedback"]).exists())
            self.assertEqual((paths["feedback"]).read_text(encoding="utf-8"), "")
            self.assertEqual([row["candidate_id"] for row in manifest["candidates"]], ["cand-a", "cand-b"])
            self.assertEqual(manifest["candidates"][0]["auto_eval"]["status"], "pass")
            self.assertEqual(manifest["candidates"][0]["material_timeline_status"], "ready")
            self.assertEqual(manifest["candidates"][0]["material_state_summary"]["delta_count"], 1)
            self.assertEqual(manifest["candidates"][0]["frames"][1]["material_timeline_frame_index"], 1)
            self.assertEqual(manifest["candidates"][1]["material_timeline_status"], "not_linked")
            self.assertEqual(manifest["candidates"][1]["auto_eval"]["status"], "reject")
            self.assertEqual(manifest["candidates"][0]["auto_eval"]["candidate_score"]["schema_version"], "candidate_score.v1")
            self.assertIn("readability", manifest["candidates"][0]["auto_eval"]["candidate_score"]["common_scores"])
            self.assertIn("scene_mismatch", manifest["candidates"][1]["auto_eval"]["hard_reject_reasons"])
            self.assertEqual(manifest["candidates"][0]["contact_sheet_page"], 1)
            self.assertEqual(manifest["candidates"][1]["contact_sheet_page"], 2)
            self.assertEqual(len(auto_eval_lines), 2)
            self.assertEqual([row["candidate_id"] for row in auto_eval_lines], ["cand-a", "cand-b"])

            for page_path in page_paths:
                self.assertTrue(page_path.exists())
                self.assertGreater(page_path.stat().st_size, 0)
                with Image.open(page_path) as image:
                    self.assertGreater(image.width, 0)
                    self.assertGreater(image.height, 0)

    def test_capture_v2_incomplete_context_is_rejected_from_image_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._make_project(root)
            run_root = root / "runs" / "capture-v2"
            prompt_path = root / "prompt.md"
            _write_text(prompt_path, "# capture v2\n")
            candidate_dir = run_root / "candidates" / "cand-v2"
            self._make_candidate(
                candidate_dir,
                candidate_id="cand-v2",
                seed=1,
                scene="CaptureV2",
                camera="Main Camera",
                render_time_points=[0.0, 0.1],
                colors=[(10, 100, 200), (20, 140, 240)],
            )
            manifest_path = candidate_dir / "capture_manifest.json"
            capture = json.loads(manifest_path.read_text(encoding="utf-8"))
            capture.update(
                {
                    "capture_pipeline_version": "play_mode_runtime_isolated_multiview.v2",
                    "distinct_instance_ids": True,
                    "technical_frame_eligible": True,
                    "image_sequence_training_eligible": False,
                    "full_visual_training_eligible": False,
                    "visual_evidence_status": "incomplete_context",
                    "context": {"status": "incomplete_context"},
                    "camera_selection": {"status": "selected_visible_view", "selected_view": "front", "candidates": []},
                }
            )
            manifest_path.write_text(json.dumps(capture), encoding="utf-8")
            paths = build_run_outputs(
                run_root,
                prompt_path=prompt_path,
                unity_project=project,
                scene="CaptureV2",
                camera="Main Camera",
                resolution=(32, 32),
                render_time_points_seconds=[0.0, 0.1],
            )
            run = json.loads(paths["run_manifest"].read_text(encoding="utf-8"))

        candidate = run["candidates"][0]
        self.assertEqual(candidate["auto_eval"]["status"], "reject")
        self.assertIn("capture_image_sequence_ineligible", candidate["auto_eval"]["hard_reject_reasons"])
        self.assertIn("capture_context_incomplete", candidate["auto_eval"]["hard_reject_reasons"])
        self.assertEqual(run["capture_evidence_summary"]["image_sequence_training_eligible_count"], 0)


if __name__ == "__main__":
    unittest.main()
