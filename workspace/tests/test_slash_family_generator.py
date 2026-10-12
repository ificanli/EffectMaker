from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.slash_family_generator import HIT_TEXTURE, SLASH_MATERIAL, SLASH_MESH, SLASH_TEXTURE, create_layered_slash


class SlashFamilyGeneratorTests(unittest.TestCase):
    def test_four_layers_use_role_specific_rendering_assets(self) -> None:
        graph = create_layered_slash("x", 7, 0)
        roles = {node["node_id"]: node["role"] for node in graph["nodes"]}
        particles = {roles[row["node_id"]]: row for row in graph["components"]["particle_systems"]}
        self.assertEqual(set(particles), {"core", "support", "hit", "residual"})
        self.assertTrue(all(particles[role]["parameters"]["renderer_mode"] == "Mesh" for role in ("core", "support")))
        self.assertTrue(all(particles[role]["mesh_paths"] == [SLASH_MESH] for role in ("core", "support")))
        self.assertTrue(all(particles[role]["parameters"]["renderer_mode"] == "Billboard" for role in ("hit", "residual")))
        self.assertTrue(all(particles[role]["mesh_paths"] == [] for role in ("hit", "residual")))
        self.assertTrue(all(row["parameters"]["material_template_path"] == SLASH_MATERIAL for row in particles.values()))
        self.assertTrue(all(particles[role]["parameters"]["texture_asset_path"] == SLASH_TEXTURE for role in ("core", "support", "residual")))
        self.assertEqual(particles["hit"]["parameters"]["texture_asset_path"], HIT_TEXTURE)
        self.assertGreater(particles["core"]["parameters"]["start_size_max"], particles["support"]["parameters"]["start_size_max"])
        self.assertGreater(particles["core"]["parameters"]["start_color_rgba"][3], particles["support"]["parameters"]["start_color_rgba"][3])
        self.assertGreater(particles["residual"]["parameters"]["start_speed_max"], 0.0)
        hit_node = next(node for node in graph["nodes"] if node["role"] == "hit")
        self.assertGreater(hit_node["transform"]["local_position"][0], 0.0)

    def test_seeded_generation_is_reproducible(self) -> None:
        self.assertEqual(create_layered_slash("x", 7, 0), create_layered_slash("x", 7, 0))
        self.assertNotEqual(create_layered_slash("x", 7, 0)["graph_id"], create_layered_slash("x", 8, 0)["graph_id"])


if __name__ == "__main__":
    unittest.main()
