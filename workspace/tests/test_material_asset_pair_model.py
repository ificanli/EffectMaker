from __future__ import annotations

import unittest
from pathlib import Path

import torch

from workspace.tools.vfx_generation.material_asset_pair_model import MaterialAssetPairModel, feature_vector, load_model


ROOT = Path(__file__).parents[2]


class MaterialAssetPairModelTests(unittest.TestCase):
    def test_feature_vector_and_forward_shape_are_stable(self) -> None:
        row = {
            "effect_type": "impact",
            "effect_element_tags": ["energy"],
            "layer_role": "hit",
            "style_family": "cartoon",
            "color_tags": ["blue"],
            "shader_id": "shader_test",
            "shader_pipeline_tags": ["builtin"],
            "texture_tags": ["slot.alpha_mask", "semantic.ring"],
            "texture_width": 256,
            "texture_height": 256,
            "material_property_count": 12,
            "shader_property_count": 10,
            "prefab_graph_usage_count": 2,
        }
        values = feature_vector(row)
        model = MaterialAssetPairModel(len(values), 16)
        logits = model(torch.tensor([values], dtype=torch.float32))
        self.assertEqual(len(values), 11 + 10 + 4 + 5 + 9 + 2 + 15 + 32 + 5)
        self.assertEqual(tuple(logits.shape), (1,))

    def test_real_checkpoint_loads_when_available(self) -> None:
        checkpoint = ROOT / "workspace/data/vfx_generation/models/material_asset_pair_full_r003/material_asset_pair_model.pt"
        if not checkpoint.is_file():
            self.skipTest("asset pair checkpoint is not available")
        model = load_model(checkpoint)
        self.assertIsInstance(model, MaterialAssetPairModel)
        self.assertFalse(model.training)


if __name__ == "__main__":
    unittest.main()
