from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_explosion_material_teacher_reproduction import (
    STRUCTURED_TEXTURE,
    _controlled_graph_comparison,
    _frame_metrics,
    _variant,
)


class ProfessionalExplosionMaterialTeacherTests(unittest.TestCase):
    def test_variants_only_change_core_texture(self) -> None:
        source = create_layered_explosion("x", 7, 0)
        original = copy.deepcopy(source)
        flat = _variant(source, "flat_glow")
        structured = _variant(source, "structured_flame")
        comparison = _controlled_graph_comparison(flat, structured)
        roles = {node["node_id"]: node["role"] for node in structured["nodes"]}
        core = next(row for row in structured["components"]["particle_systems"] if roles[row["node_id"]] == "core")
        self.assertTrue(comparison["only_core_texture_differs"])
        self.assertEqual(core["parameters"]["texture_asset_path"], STRUCTURED_TEXTURE)
        self.assertEqual(source, original)

    def test_structured_mask_has_lower_fill_and_higher_variation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            flat_path, structured_path = root / "flat.png", root / "structured.png"
            flat = Image.new("RGB", (128, 128), "black")
            ImageDraw.Draw(flat).ellipse((24, 24, 104, 104), fill="white")
            flat.save(flat_path)
            structured = Image.new("RGB", (128, 128), "black")
            draw = ImageDraw.Draw(structured)
            draw.polygon(((64, 10), (78, 50), (116, 64), (76, 78), (64, 116), (50, 78), (12, 64), (50, 50)), fill="white")
            draw.ellipse((52, 52, 76, 76), fill="gray")
            structured.save(structured_path)
            flat_metrics = _frame_metrics(flat_path)
            structured_metrics = _frame_metrics(structured_path)
        self.assertLess(structured_metrics["bbox_fill_ratio"], flat_metrics["bbox_fill_ratio"])
        self.assertGreater(structured_metrics["visible_luma_std"], flat_metrics["visible_luma_std"])
        self.assertGreater(structured_metrics["edge_density"], flat_metrics["edge_density"])


if __name__ == "__main__":
    unittest.main()
