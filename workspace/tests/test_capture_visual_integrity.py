from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from workspace.tools.vfx_generation.capture_visual_integrity import analyze_frame


class CaptureVisualIntegrityTests(unittest.TestCase):
    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).parents[2]

    def test_unity_error_magenta_is_a_technical_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "magenta.png"
            pixels = np.zeros((100, 100, 3), dtype=np.uint8)
            pixels[25:75, 25:75] = [255, 0, 255]
            Image.fromarray(pixels, "RGB").save(path)
            result = analyze_frame(path)
        self.assertTrue(result["unity_error_magenta"])
        self.assertAlmostEqual(result["error_magenta_ratio"], 0.25)
        self.assertAlmostEqual(result["error_magenta_visible_ratio"], 1.0)

    def test_normal_purple_gradient_is_not_error_magenta(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "purple.png"
            pixels = np.zeros((100, 100, 3), dtype=np.uint8)
            pixels[25:75, 25:75] = [190, 45, 230]
            Image.fromarray(pixels, "RGB").save(path)
            result = analyze_frame(path)
        self.assertFalse(result["unity_error_magenta"])
        self.assertEqual(result["error_magenta_pixel_count"], 0)

    def test_real_missing_material_frame_is_a_technical_exclusion(self) -> None:
        path = self._repo_root() / "workspace/data/vfx_generation/captures/full_prefab_capture_r002/cases/full_prefab_0011_b7cb452d9bf1/captures/frame_016_1_600.png"
        self.assertTrue(path.is_file(), path)
        result = analyze_frame(path)
        self.assertTrue(result["unity_error_magenta"])
        self.assertGreater(result["error_magenta_visible_ratio"], 0.99)

    def test_real_pink_effect_is_not_mistaken_for_missing_material(self) -> None:
        path = self._repo_root() / "workspace/data/vfx_generation/captures/full_prefab_capture_r002/cases/full_prefab_0002_62aa9ecfed9f/captures/frame_000_0_000.png"
        self.assertTrue(path.is_file(), path)
        result = analyze_frame(path)
        self.assertFalse(result["unity_error_magenta"])
        self.assertGreater(result["error_magenta_pixel_count"], 64)
        self.assertLess(result["error_magenta_visible_ratio"], 0.05)


if __name__ == "__main__":
    unittest.main()
