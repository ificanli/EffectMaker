from __future__ import annotations

import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.explosion_family_generator import CORE_TEXTURE_CANDIDATE, create_layered_explosion, generate_batch
from workspace.tools.vfx_generation.prefab_graph import _read_json, _schema_root


class ExplosionFamilyGeneratorTests(unittest.TestCase):
    def test_four_roles_have_distinct_assets_and_staggered_timing(self) -> None:
        graph = create_layered_explosion("卡通橙色能量爆炸", 7, 0)
        roles = {node["node_id"]: node["role"] for node in graph["nodes"]}
        particles = {roles[row["node_id"]]: row["parameters"] for row in graph["components"]["particle_systems"]}

        self.assertEqual(set(particles), {"core", "support", "hit", "residual"})
        self.assertEqual(len({row["texture_asset_path"] for row in particles.values()}), 4)
        self.assertGreaterEqual(len({row["material_template_path"] for row in particles.values()}), 3)
        self.assertLess(particles["core"]["start_delay_max"], particles["support"]["start_delay_max"])
        self.assertLess(particles["support"]["start_delay_max"], particles["residual"]["start_delay_max"])
        self.assertGreater(particles["support"]["end_size_multiplier"], particles["core"]["end_size_multiplier"])
        self.assertGreater(particles["hit"]["start_speed_max"], particles["residual"]["start_speed_max"])
        self.assertEqual(graph["nodes"][0]["name"], "GeneratedRoot")
        self.assertTrue(all(node["hierarchy_path"].startswith("GeneratedRoot[0]") for node in graph["nodes"]))
        Draft202012Validator(_read_json(_schema_root() / "prefab_graph.schema.json")).validate(graph)

    def test_seeded_generation_is_reproducible_and_varies_by_seed(self) -> None:
        first = create_layered_explosion("x", 7, 1)
        repeated = create_layered_explosion("x", 7, 1)
        other = create_layered_explosion("x", 8, 2)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first["graph_id"], other["graph_id"])

    def test_structured_core_texture_is_explicit_opt_in(self) -> None:
        default = create_layered_explosion("x", 7, 0)
        structured = create_layered_explosion("x", 7, 0, "structured_flame")
        roles = {node["node_id"]: node["role"] for node in structured["nodes"]}
        structured_core = next(row for row in structured["components"]["particle_systems"] if roles[row["node_id"]] == "core")
        default_core = next(row for row in default["components"]["particle_systems"] if roles[row["node_id"]] == "core")
        self.assertEqual(structured_core["parameters"]["texture_asset_path"], CORE_TEXTURE_CANDIDATE)
        self.assertNotEqual(default_core["parameters"]["texture_asset_path"], CORE_TEXTURE_CANDIDATE)
        self.assertNotEqual(default["graph_id"], structured["graph_id"])


if __name__ == "__main__":
    unittest.main()
