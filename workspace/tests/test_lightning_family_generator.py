from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.lightning_family_generator import HIT_TEXTURE, MAIN_BOLT_TEXTURE, SPARK_TEXTURE, create_layered_lightning


class LightningFamilyGeneratorTests(unittest.TestCase):
    def test_four_layers_have_distinct_roles_and_textures(self) -> None:
        graph = create_layered_lightning("x", 7, 0)
        roles = {node["node_id"]: node["role"] for node in graph["nodes"]}
        particles = {roles[row["node_id"]]: row for row in graph["components"]["particle_systems"]}
        self.assertEqual(set(particles), {"core", "support", "hit", "residual"})
        self.assertEqual(particles["core"]["parameters"]["texture_asset_path"], MAIN_BOLT_TEXTURE)
        self.assertEqual(particles["hit"]["parameters"]["texture_asset_path"], HIT_TEXTURE)
        self.assertEqual(particles["residual"]["parameters"]["texture_asset_path"], SPARK_TEXTURE)
        self.assertTrue(all(row["parameters"]["renderer_mode"] == "Billboard" for row in particles.values()))
        self.assertGreaterEqual(particles["core"]["parameters"]["start_size_max"], particles["support"]["parameters"]["start_size_max"] * 1.2)
        self.assertGreaterEqual(particles["core"]["parameters"]["start_color_rgba"][3], particles["support"]["parameters"]["start_color_rgba"][3] * 2.0)
        self.assertGreater(particles["residual"]["parameters"]["start_speed_max"], 0.0)

    def test_seeded_generation_is_reproducible(self) -> None:
        self.assertEqual(create_layered_lightning("x", 7, 0), create_layered_lightning("x", 7, 0))
        self.assertNotEqual(create_layered_lightning("x", 7, 0)["graph_id"], create_layered_lightning("x", 8, 0)["graph_id"])


if __name__ == "__main__":
    unittest.main()
