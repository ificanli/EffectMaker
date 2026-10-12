from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_residual_teacher_reproduction import _graph_comparison, _variant
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashResidualTeacherTests(unittest.TestCase):
    def test_variants_only_change_residual_timing(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        premature = _variant(source, "premature_residual")
        staged = _variant(source, "staged_residual")
        comparison = _graph_comparison(premature, staged)
        self.assertTrue(comparison["only_residual_timing_differs"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
