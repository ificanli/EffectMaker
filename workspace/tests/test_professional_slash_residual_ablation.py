from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_residual_ablation import create_premature_ablation
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashResidualAblationTests(unittest.TestCase):
    def test_ablation_only_changes_residual_timing(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_premature_ablation(source)
        roles = {node["node_id"]: node["role"] for node in baseline["nodes"]}
        residual = next(row for row in baseline["components"]["particle_systems"] if roles[row["node_id"]] == "residual")
        self.assertEqual(residual["parameters"]["start_delay_max"], 0.0)
        self.assertEqual(residual["parameters"]["start_lifetime_max"], 0.12)
        self.assertEqual(changed, ["residual.start_delay_max", "residual.start_lifetime_max"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
