from __future__ import annotations

import json
import unittest
from pathlib import Path

import torch
from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.visual_dynamics_model import VisualDynamicsModel, feature_vector


ROOT = Path(__file__).parents[2]


class VisualDynamicsTrainingViewTests(unittest.TestCase):
    def test_schema_blocks_quality_head_without_teacher(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/visual_dynamics_training_view.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["quality_gates"]["properties"]["professional_quality_labels_consumed"]["const"], 0)
        self.assertEqual(schema["properties"]["training_policy"]["properties"]["visible_is_not_quality"]["const"], True)
        self.assertIsInstance(Draft202012Validator(schema), Draft202012Validator)

    def test_technical_dynamics_model_has_no_quality_output(self) -> None:
        row = {
            "effect_type": "impact",
            "style_family": "cartoon",
            "sample_kind": "generated_prefab",
            "image_features": {"image.visible_ratio.mean": 0.1},
            "material_timeline": {"frame_count": 14, "delta_count": 2, "changed_frame_count": 2, "has_dynamic_material_state": True, "has_unenumerated_property_block_values": False, "global_shader_state_status": "not_instrumented"},
        }
        values = feature_vector(row)
        model = VisualDynamicsModel(len(values), 16)
        dynamic, delta = model(torch.tensor([values], dtype=torch.float32))
        self.assertEqual(tuple(dynamic.shape), (1,))
        self.assertEqual(tuple(delta.shape), (1,))
        self.assertFalse(hasattr(model, "quality_head"))


if __name__ == "__main__":
    unittest.main()
