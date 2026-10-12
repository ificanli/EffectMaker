import unittest

from workspace.tools.vfx_generation.generator_registry import generator_catalog, get_generator_family, require_production_ready


class GeneratorRegistryTests(unittest.TestCase):
    def test_catalog_defines_multiple_family_specific_candidate_spaces(self):
        catalog = generator_catalog()
        self.assertEqual(catalog["schema_version"], "vfx_generator_registry.v2")
        self.assertGreaterEqual(catalog["family_count"], 6)
        self.assertEqual(catalog["technical_adapter_families"], ["explosion", "lightning", "slash"])
        self.assertEqual(catalog["production_ready_families"], [])
        self.assertEqual(catalog["migration_required_families"], ["explosion", "lightning", "slash"])
        for family in ("slash", "fire", "lightning", "shield", "smoke", "explosion"):
            entry = get_generator_family(family)
            self.assertTrue(entry["inputs"])
            self.assertTrue(entry["outputs"])
            self.assertTrue(entry["applies_to"])
            self.assertTrue(entry["failure_modes"])
            self.assertFalse(entry["production_generation_eligible"])
            self.assertTrue(entry["migration_blockers"])
        self.assertEqual(get_generator_family("slash")["generator_family"], "mesh_blade_multilayer")
        self.assertEqual(get_generator_family("slash")["generator_module"], "workspace.tools.vfx_generation.slash_family_generator")
        self.assertEqual(get_generator_family("lightning")["implementation_status"], "legacy_fixed_adapter")
        self.assertFalse(get_generator_family("lightning")["proposal_planner_ready"])
        self.assertEqual(get_generator_family("lightning")["generator_module"], "workspace.tools.vfx_generation.lightning_family_generator")

    def test_unknown_family_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown generator family"):
            get_generator_family("unknown")

    def test_legacy_fixed_adapters_cannot_be_used_as_production_prompt_generators(self):
        for family in ("slash", "lightning", "explosion"):
            with self.assertRaisesRegex(ValueError, "not production-ready"):
                require_production_ready(family)


if __name__ == "__main__":
    unittest.main()
