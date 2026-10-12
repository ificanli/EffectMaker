from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_rhythm_ablation import create_simultaneous_ablation
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashRhythmAblationTests(unittest.TestCase):
    def test_ablation_only_zeros_non_core_delays(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_simultaneous_ablation(source)
        roles = {node["node_id"]: node["role"] for node in baseline["nodes"]}
        delays = {roles[row["node_id"]]: row["parameters"]["start_delay_max"] for row in baseline["components"]["particle_systems"]}
        self.assertEqual(delays, {"core": 0.0, "support": 0.0, "hit": 0.0, "residual": 0.0})
        self.assertEqual(set(changed), {"support.parameters.start_delay_max", "hit.parameters.start_delay_max", "residual.parameters.start_delay_max"})
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
