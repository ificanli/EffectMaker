from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.style_profile import parse_style_profile


class VfxStyleProfileTests(unittest.TestCase):
    def test_parses_chinese_cartoon_style(self) -> None:
        profile = parse_style_profile("高饱和卡通火焰爆炸", scene_context=["battle"])

        self.assertEqual(profile["family"], "cartoon")
        self.assertIn("卡通", profile["keywords"])
        self.assertEqual(profile["scene_context"], ["battle"])
        self.assertGreater(profile["axes"]["graphic_stylization"], 0.8)

    def test_parses_mixed_style_without_discarding_keywords(self) -> None:
        profile = parse_style_profile("写实但带二次元高光的技能特效")

        self.assertEqual(profile["family"], "mixed")
        self.assertEqual(set(profile["keywords"]), {"写实", "二次元"})
        self.assertGreater(profile["confidence"], 0.5)

    def test_keeps_unknown_style_unlabeled(self) -> None:
        profile = parse_style_profile("向前冲击的火球")

        self.assertEqual(profile["family"], "unknown")
        self.assertEqual(profile["confidence"], 0.0)
        self.assertTrue(profile["notes"])


if __name__ == "__main__":
    unittest.main()
