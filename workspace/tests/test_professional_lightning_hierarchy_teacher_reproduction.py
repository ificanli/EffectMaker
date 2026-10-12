from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning
from workspace.tools.vfx_generation.professional_lightning_hierarchy_teacher_reproduction import _graph_comparison, _variant


class ProfessionalLightningHierarchyTeacherTests(unittest.TestCase):
    def test_variants_only_change_branch_size_and_alpha(self) -> None:
        source = create_layered_lightning("x", 7, 0)
        original = copy.deepcopy(source)
        equal = _variant(source, "equal_weight")
        dominant = _variant(source, "main_dominant")
        comparison = _graph_comparison(equal, dominant)
        self.assertTrue(comparison["only_branch_size_and_alpha_differ"])
        for graph in (equal, dominant):
            roles = {node["role"]: node for node in graph["nodes"]}
            self.assertFalse(roles["hit"]["active_self"])
            self.assertFalse(roles["residual"]["active_self"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
