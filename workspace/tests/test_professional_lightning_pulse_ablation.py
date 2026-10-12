from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning
from workspace.tools.vfx_generation.professional_lightning_pulse_ablation import create_instant_isolated, create_slow_pulse_ablation


class ProfessionalLightningPulseAblationTests(unittest.TestCase):
    def test_ablation_only_extends_core_lifetime(self) -> None:
        source = create_layered_lightning("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_slow_pulse_ablation(source)
        roles = {node["node_id"]: node["role"] for node in baseline["nodes"]}
        core = next(row for row in baseline["components"]["particle_systems"] if roles[row["node_id"]] == "core")
        self.assertEqual(core["parameters"]["start_lifetime_max"], 0.36)
        self.assertEqual(changed, ["core.parameters.start_lifetime_max"])
        self.assertEqual(source, original)

    def test_guided_variant_isolates_core(self) -> None:
        guided = create_instant_isolated(create_layered_lightning("x", 7, 0))
        roles = {node["role"]: node for node in guided["nodes"]}
        self.assertTrue(roles["core"]["active_self"])
        for role in ("support", "hit", "residual"):
            self.assertFalse(roles[role]["active_self"])


if __name__ == "__main__":
    unittest.main()
