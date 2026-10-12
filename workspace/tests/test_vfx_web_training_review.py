from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.feedback import validate_feedback_record
from workspace.tools.vfx_web_training_review import (
    build_asset_map,
    build_catalog_manifest,
    build_review_bundle,
    validate_bundle,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class VfxWebTrainingReviewTests(unittest.TestCase):
    def test_builds_web_review_bundle_with_material_change_times(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_root = root / "runs" / "runtime-r001"
            candidate_root = run_root / "candidates" / "candidate-a"
            _write_json(
                candidate_root / "spec.json",
                {
                    "schema_version": "vfxspec.v1",
                    "effect_family": "fire",
                    "training_case_id": "case-fire-a",
                    "generation": {
                        "candidate_id": "candidate-a",
                        "seed": 7,
                        "generator": "source_prefab_render",
                        "generator_version": "1.0",
                    },
                    "layers": [
                        {
                            "shape_parameters": {
                                "source_prefab_path": "Assets/VFXSourceIngest/Fire.prefab"
                            }
                        }
                    ],
                },
            )
            _write_json(
                candidate_root / "material_timeline.json",
                {
                    "schema": "vfx-material-timeline.v1",
                    "source_script_fidelity": "source_scripts_excluded",
                    "frames": [
                        {"capture_time_seconds": 0.0, "deltas_from_previous": []},
                        {"capture_time_seconds": 0.2, "deltas_from_previous": [{"change_type": "texture_changed"}]},
                        {"capture_time_seconds": 0.4, "deltas_from_previous": [{"change_type": "dissolve_parameter_changed"}]},
                    ],
                },
            )
            _write_json(
                candidate_root / "capture_manifest.json",
                {"material_timeline_path": "material_timeline.json"},
            )
            run_manifest = run_root / "run_manifest.json"
            _write_json(
                run_manifest,
                {
                    "run_id": "runtime-r001",
                    "unity_project": "E:/Unity/EffectDemo",
                    "capture_mode": "play_mode_runtime",
                    "candidates": [
                        {
                            "candidate_id": "candidate-a",
                            "seed": 7,
                            "material_timeline_status": "ready",
                            "spec_path": "candidates/candidate-a/spec.json",
                            "render_manifest_path": "candidates/candidate-a/capture_manifest.json",
                            "spec_summary": {"effect_family": "fire"},
                        }
                    ],
                },
            )
            asset_map = root / "asset-map.json"
            _write_json(
                asset_map,
                {
                    "schemaVersion": "vfx_web_training_asset_map.v1",
                    "reviewBundleId": "runtime-r001-review",
                    "mappings": [
                        {
                            "candidateId": "candidate-a",
                            "webPrefabPath": "Assets/Art/VFX/Training/Fire.prefab",
                        }
                    ],
                },
            )

            bundle = build_review_bundle(run_manifest, asset_map)
            validate_bundle(bundle)

            self.assertEqual(bundle["truthCaptureMode"], "play_mode_runtime")
            self.assertEqual(bundle["entries"][0]["materialTimelineStatus"], "ready")
            self.assertEqual(bundle["entries"][0]["materialChangeCount"], 2)
            self.assertEqual(bundle["entries"][0]["materialKeyTimes"], [0.2, 0.4])
            self.assertEqual(bundle["entries"][0]["sourceScriptFidelity"], "source_scripts_excluded")
            self.assertEqual(bundle["entries"][0]["trainingCaseId"], "case-fire-a")

            generated_map = build_asset_map(run_manifest)
            self.assertEqual(generated_map["mappings"], [{
                "candidateId": "candidate-a",
                "webPrefabPath": "Assets/VFXSourceIngest/Fire.prefab",
                "sourcePrefabPath": "Assets/VFXSourceIngest/Fire.prefab",
            }])
            generated_map_path = root / "generated-map.json"
            _write_json(generated_map_path, generated_map)
            unity_project = root / "EffectDemo"
            prefab_path = unity_project / "Assets" / "VFXSourceIngest" / "Fire.prefab"
            prefab_path.parent.mkdir(parents=True, exist_ok=True)
            prefab_path.write_text("%YAML 1.1\n", encoding="utf-8")
            Path(str(prefab_path) + ".meta").write_text(
                "fileFormatVersion: 2\nguid: 0123456789abcdef0123456789abcdef\n",
                encoding="utf-8",
            )
            catalog = build_catalog_manifest(generated_map_path, unity_project, "http://127.0.0.1:8775/")
            self.assertEqual(catalog["entries"][0]["catalogId"], "0123456789abcdef0123456789abcdef")
            self.assertEqual(catalog["playerUrl"], "http://127.0.0.1:8775/")

    def test_web_feedback_schema_accepts_dynamic_review_context(self) -> None:
        schema_path = Path("workspace/data/vfx_generation/schemas/vfx_web_training_feedback.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        record = {
            "schema_version": "human_feedback.v1",
            "run_id": "runtime-r001",
            "candidate_id": "candidate-a",
            "training_case_id": "case-fire-a",
            "reviewed_at": "2026-08-28T00:00:00+00:00",
            "reviewer": "human",
            "decision": "partial",
            "mutation_allowed": True,
            "style_match_decision": "unlabeled",
            "scores": {"dynamic_quality": 3, "rhythm_quality": 4},
            "trace": {
                "spec_path": "candidates/candidate-a/spec.json",
                "render_manifest_path": "candidates/candidate-a/capture_manifest.json",
                "render_paths": [],
                "seed": 7,
                "generator": "source_prefab_render",
                "generator_version": "1.0",
                "render_status": "ready",
                "material_timeline_path": "candidates/candidate-a/material_timeline.json",
            },
            "feedback": {
                "summary": "峰值时材质变化正确，但消散过快。",
                "accepted_parts": [],
                "rejected_parts": [],
                "reject_reasons": [],
                "next_mutation": [],
            },
            "web_review_context": {
                "web_prefab_id": "fire",
                "web_prefab_path": "Assets/Art/VFX/Training/Fire.prefab",
                "source_prefab_path": "Assets/VFXSourceIngest/Fire.prefab",
                "observed_time_seconds": 0.4,
                "paused": True,
                "speed": 1.0,
                "material_state_fingerprint": "abc",
                "webgl_material_state_changes": 2,
                "truth_material_change_count": 2,
                "source_script_fidelity": "source_scripts_excluded",
                "evidence_role": "dynamic_human_review_only",
            },
        }

        errors = list(Draft202012Validator(schema).iter_errors(record))
        self.assertEqual(errors, [])
        self.assertEqual(
            validate_feedback_record(
                record,
                expected_run_id="runtime-r001",
                candidate_ids={"candidate-a"},
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
