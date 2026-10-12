from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_explosion_rhythm_teacher_reproduction import _controlled_graph_comparison, _variant


class ProfessionalExplosionRhythmTeacherTests(unittest.TestCase):
    def test_variants_only_change_three_layer_delays(self) -> None:
        source = create_layered_explosion("x", 7, 0, "structured_flame")
        original = copy.deepcopy(source)
        simultaneous = _variant(source, "simultaneous_layers")
        staged = _variant(source, "staged_layers")
        comparison = _controlled_graph_comparison(simultaneous, staged)
        self.assertTrue(comparison["only_layer_delays_differ"])
        self.assertEqual(len(comparison["difference_paths"]), 3)
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
