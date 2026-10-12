from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_explosion_material_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalExplosionMaterialRuleModelTests(unittest.TestCase):
    def test_feature_vector_is_core_local_and_stable(self) -> None:
        vector = feature_vector({"image_features": {FEATURE_NAMES[0]: 0.2, FEATURE_NAMES[-1]: 0.8}})
        self.assertTrue(all(name.startswith("core.") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.2)
        self.assertEqual(vector[-1], 0.8)
        self.assertEqual(sum(vector[1:-1]), 0.0)


if __name__ == "__main__":
    unittest.main()
