from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


class VfxMaterialTimelineSchemaTests(unittest.TestCase):
    def test_schema_accepts_material_mpb_texture_keyword_and_dissolve_delta(self) -> None:
        schema = json.loads(
            Path("workspace/data/vfx_generation/schemas/material_timeline.schema.json").read_text(encoding="utf-8")
        )
        property_state = {
            "property_name": "_DissolveAmount",
            "property_id": 1,
            "display_name": "Dissolve Amount",
            "property_type": "float",
            "flags": [],
            "semantic_tags": ["dissolve"],
            "source": "slot_property_block",
            "value_kind": "float",
            "numeric_value": [0.5],
            "texture_value": None,
            "texture_scale": None,
            "texture_offset": None,
            "canonical_value": "0.5",
        }
        timeline = {
            "schema_version": "vfx_material_timeline.v1",
            "created_at": "2026-08-28T00:00:00Z",
            "candidate_id": "material-probe",
            "prefab_path": "Assets/VFXCapture/Tests/MaterialProbe.prefab",
            "capture_mode": "play_mode_runtime",
            "capture_order": "late_update_barrier -> material_snapshot -> camera_render",
            "primary_training_signal": "runtime_material_state",
            "visual_evidence_role": "frame_alignment_only",
            "source_script_fidelity": "source_scripts_captured",
            "ignored_script_dependency_count": 0,
            "limitations": [],
            "summary": {
                "frame_count": 2,
                "renderer_count_peak": 1,
                "material_slot_count_peak": 1,
                "delta_count": 1,
                "changed_frame_count": 1,
                "has_dynamic_material_state": True,
                "has_unenumerated_property_block_values": False,
                "global_shader_state_status": "instrumented",
                "global_shader_value_count": 1,
                "global_shader_delta_count": 1,
                "key_material_change_times": [0.1],
                "signal_counts": [{"signal": "dissolve_parameter_changed", "count": 1}],
            },
            "frames": [
                {
                    "frame_index": 0,
                    "unity_frame_count": 1,
                    "requested_time_seconds": 0.0,
                    "capture_time_seconds": 0.0,
                    "image_path": "frame_000.png",
                    "global_shader_state_status": "instrumented",
                    "global_shader_values": [{"property_name": "_EffectDemoTrackedGlobalAlpha", "property_id": 12, "value_kind": "float", "numeric_value": [1.0], "canonical_value": "1", "revision": 1, "writer": "probe"}],
                    "renderers": [],
                    "deltas_from_previous": [],
                },
                {
                    "frame_index": 1,
                    "unity_frame_count": 2,
                    "requested_time_seconds": 0.1,
                    "capture_time_seconds": 0.1,
                    "image_path": "frame_001.png",
                    "global_shader_state_status": "instrumented",
                    "global_shader_values": [{"property_name": "_EffectDemoTrackedGlobalAlpha", "property_id": 12, "value_kind": "float", "numeric_value": [0.5], "canonical_value": "0.5", "revision": 2, "writer": "probe"}],
                    "renderers": [
                        {
                            "hierarchy_path": "Root[0]/Quad[0]",
                            "renderer_type": "MeshRenderer",
                            "renderer_instance_id": 2,
                            "enabled": True,
                            "active_in_hierarchy": True,
                            "material_slots": [
                                {
                                    "slot_index": 0,
                                    "material_missing": False,
                                    "material_instance_id": 3,
                                    "material_name": "Probe",
                                    "material_asset_path": "",
                                    "shader_name": "VFX/Probe",
                                    "shader_asset_path": "Assets/VFX/Probe.shader",
                                    "render_queue": 3000,
                                    "shader_keywords": ["PROBE_FLOW_ON"],
                                    "material_properties": [],
                                    "renderer_property_block": {"is_empty": True, "has_unenumerated_values": False, "properties": []},
                                    "slot_property_block": {"is_empty": False, "has_unenumerated_values": False, "properties": [property_state]},
                                    "active_property_block_scope": "slot",
                                }
                            ],
                        }
                    ],
                    "deltas_from_previous": [
                        {
                            "categories": ["slot_property_block_changed", "dissolve_parameter_changed"],
                            "renderer_path": "Root[0]/Quad[0]",
                            "material_slot": 0,
                            "property_name": "_DissolveAmount",
                            "semantic_tags": ["dissolve"],
                            "before_value": "0",
                            "after_value": "0.5",
                        }
                    ],
                },
            ],
        }

        errors = list(Draft202012Validator(schema).iter_errors(timeline))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
