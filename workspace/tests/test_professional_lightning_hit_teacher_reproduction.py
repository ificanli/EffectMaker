from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning
from workspace.tools.vfx_generation.professional_lightning_hit_teacher_reproduction import _graph_comparison, _variant


class ProfessionalLightningHitTeacherTests(unittest.TestCase):
    def test_variants_only_change_hit_alpha(self) -> None:
        source = create_layered_lightning("x", 7, 0)
        original = copy.deepcopy(source)
        weak = _variant(source, "weak_impact")
        focused = _variant(source, "focused_impact")
        comparison = _graph_comparison(weak, focused)
        self.assertTrue(comparison["only_hit_alpha_differs"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
