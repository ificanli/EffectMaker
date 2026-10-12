from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_explosion_rhythm_ablation import create_simultaneous_ablation


class ProfessionalExplosionRhythmAblationTests(unittest.TestCase):
    def test_ablation_only_zeroes_non_core_delays(self) -> None:
        source = create_layered_explosion("x", 7, 0, "structured_flame")
        original = copy.deepcopy(source)
        baseline, changed = create_simultaneous_ablation(source)
        roles = {node["node_id"]: node["role"] for node in baseline["nodes"]}
        delays = {roles[row["node_id"]]: row["parameters"]["start_delay_max"] for row in baseline["components"]["particle_systems"]}
        self.assertEqual(delays["core"], 0.0)
        self.assertEqual(delays["support"], 0.0)
        self.assertEqual(delays["hit"], 0.0)
        self.assertEqual(delays["residual"], 0.0)
        self.assertEqual(len(changed), 3)
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
