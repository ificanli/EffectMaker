from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_debris_teacher_reproduction import (
    _connected_components,
    _controlled_graph_comparison,
    _difference_metrics,
    _variant,
)


class ProfessionalDebrisTeacherReproductionTests(unittest.TestCase):
    def test_variants_only_change_debris_alpha(self) -> None:
        source = create_layered_explosion("x", 7, 0)
        original = copy.deepcopy(source)
        no_debris = _variant(source, "no_debris")
        radial = _variant(source, "radial_debris")
        comparison = _controlled_graph_comparison(no_debris, radial)

        self.assertTrue(comparison["only_debris_alpha_differs"])
        self.assertEqual(source, original)

    def test_component_and_radius_metrics_detect_fragments(self) -> None:
        mask = np.zeros((32, 32), dtype=bool)
        mask[2:5, 2:5] = True
        mask[14:18, 14:18] = True
        mask[26:29, 26:29] = True
        self.assertEqual(_connected_components(mask), 3)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            left_path, right_path = root / "left.png", root / "right.png"
            Image.new("RGB", (128, 128), "black").save(left_path)
            right = Image.new("RGB", (128, 128), "black")
            draw = ImageDraw.Draw(right)
            for x, y in ((16, 16), (64, 20), (108, 64), (30, 100), (96, 100)):
                draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="white")
            right.save(right_path)
            metrics = _difference_metrics(left_path, right_path)

        self.assertGreaterEqual(metrics["component_count"], 5)
        self.assertGreater(metrics["radius_p90"], 0.4)


if __name__ == "__main__":
    unittest.main()
