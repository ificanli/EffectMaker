from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_lightning_hit_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalLightningHitRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_hit_alpha_and_visual_focus(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 1.0, FEATURE_NAMES[-1]: 4.0}})
        self.assertEqual(FEATURE_NAMES[0], "hit.alpha")
        self.assertTrue(any(name.startswith("visual.contact") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 1.0)
        self.assertEqual(vector[-1], 4.0)


if __name__ == "__main__":
    unittest.main()
