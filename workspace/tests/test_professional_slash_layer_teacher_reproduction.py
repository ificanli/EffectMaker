from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_layer_teacher_reproduction import _graph_comparison, _variant
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashLayerTeacherTests(unittest.TestCase):
    def test_variants_only_change_inner_size_and_alpha(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        equal = _variant(source, "equal_layers")
        dominant = _variant(source, "outer_dominant")
        comparison = _graph_comparison(equal, dominant)
        self.assertTrue(comparison["only_inner_size_and_alpha_differ"])
        self.assertEqual(len(comparison["difference_paths"]), 2)
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
