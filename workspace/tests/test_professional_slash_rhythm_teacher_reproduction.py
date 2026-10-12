from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_rhythm_teacher_reproduction import _graph_comparison, _variant
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashRhythmTeacherTests(unittest.TestCase):
    def test_variants_only_change_layer_delays(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        simultaneous = _variant(source, "simultaneous_layers")
        staged = _variant(source, "staged_layers")
        comparison = _graph_comparison(simultaneous, staged)
        self.assertTrue(comparison["only_layer_delays_differ"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
