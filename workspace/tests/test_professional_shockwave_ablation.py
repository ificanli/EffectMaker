from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_shockwave_ablation import (
    _difference_frame_metrics,
    create_shockwave_ablation,
)


class ProfessionalShockwaveAblationTests(unittest.TestCase):
    def test_ablation_only_makes_shockwave_static(self) -> None:
        source = create_layered_explosion("x", 7, 0)
        original = copy.deepcopy(source)
        ablation, changed = create_shockwave_ablation(source)
        roles = {node["node_id"]: node["role"] for node in ablation["nodes"]}
        support = next(row for row in ablation["components"]["particle_systems"] if roles[row["node_id"]] == "support")

        self.assertEqual(support["parameters"]["end_size_multiplier"], 1.0)
        self.assertEqual(changed, ["support.parameters.end_size_multiplier"])
        self.assertEqual(source, original)
        self.assertNotEqual(ablation["graph_id"], source["graph_id"])

    def test_difference_radius_follows_changed_outer_ring(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            static_path = root / "static.png"
            expanding_path = root / "expanding.png"
            static = Image.new("RGB", (128, 128), "black")
            expanding = static.copy()
            draw = ImageDraw.Draw(expanding)
            draw.ellipse((18, 18, 110, 110), outline="white", width=4)
            static.save(static_path)
            expanding.save(expanding_path)

            metrics = _difference_frame_metrics(static_path, expanding_path)

        self.assertGreater(metrics["difference_visible_area_ratio"], 0.0)
        self.assertGreater(metrics["difference_radius_p90"], 0.4)
        self.assertGreater(metrics["difference_radial_span"], 0.0)
        self.assertGreater(metrics["difference_mae"], 0.0)


if __name__ == "__main__":
    unittest.main()
