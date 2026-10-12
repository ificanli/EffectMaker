from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_shockwave_teacher_reproduction import (
    _controlled_graph_comparison,
    _radial_frame_metrics,
    _variant,
)


class ProfessionalShockwaveTeacherReproductionTests(unittest.TestCase):
    def test_only_shockwave_scale_curve_changes(self) -> None:
        source = create_layered_explosion("x", 7, 0)
        static = _variant(source, "static_ring")
        expanding = _variant(source, "expanding_ring")
        comparison = _controlled_graph_comparison(static, expanding)

        self.assertTrue(comparison["only_shockwave_scale_curve_differs"])
        self.assertEqual(comparison["difference_paths"], ["components.particle_systems[1].parameters.end_size_multiplier"])
        self.assertTrue(all(not node["active_self"] for node in static["nodes"] if node["role"] in {"core", "hit", "residual"}))

    def test_radial_metric_detects_larger_ring(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            small_path, large_path = root / "small.png", root / "large.png"
            for path, radius in ((small_path, 12), (large_path, 30)):
                image = Image.new("RGB", (100, 100), (0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.ellipse((50 - radius, 50 - radius, 50 + radius, 50 + radius), outline=(255, 255, 255), width=3)
                image.save(path)
            small = _radial_frame_metrics(small_path)
            large = _radial_frame_metrics(large_path)

        self.assertGreater(large["visible_radius_p90"], small["visible_radius_p90"] + 0.2)


if __name__ == "__main__":
    unittest.main()
