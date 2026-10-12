import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.slash_arc_generator import GeneratorConfig, generate_candidates, write_run


class SlashArcGeneratorTests(unittest.TestCase):
    def make_config(self, root: Path, count: int = 16, seed: int = 20260827) -> GeneratorConfig:
        return GeneratorConfig(
            run_id="slash_arc_pref_001_r001",
            count=count,
            seed=seed,
            output_dir=root / "slash_arc_pref_001_r001",
            prompt="stylized top-down slash core arc",
            negative_prompt="closed ring, symmetric UI icon, reused V9 arc",
        )

    def test_generates_reproducible_candidates_with_required_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.make_config(Path(tmp), count=16, seed=1234)
            candidates = generate_candidates(config)
            repeated = generate_candidates(config)

        self.assertEqual(candidates, repeated)
        self.assertEqual(len(candidates), 16)
        self.assertEqual(len({c["generation"]["candidate_id"] for c in candidates}), 16)
        self.assertEqual({c["effect_family"] for c in candidates}, {"slash"})
        self.assertEqual({c["adapter"]["name"] for c in candidates}, {"slash.adapter"})
        self.assertEqual({c["adapter"]["schema_ref"] for c in candidates}, {"schemas/adapters/slash_adapter.schema.json"})
        self.assertEqual({c["render_plan"]["unity_project"] for c in candidates}, {"E:/Unity特效人工智能学习/UnityDemo/EffectDemo"})
        self.assertEqual({c["material_profile"]["shader"]["name"] for c in candidates}, {"Universal Render Pipeline/Particles/Unlit"})
        self.assertEqual({c["layers"][0]["role"] for c in candidates}, {"core_blade"})
        self.assertEqual({c["layers"][0]["status"] for c in candidates}, {"active"})
        self.assertEqual({c["target_style_profile"]["family"] for c in candidates}, {"stylized"})

    def test_covers_four_topologies_and_shape_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidates = generate_candidates(self.make_config(Path(tmp), count=20))

        topologies = {c["adapter"]["topology"]["arc_topology"] for c in candidates}
        self.assertGreaterEqual(len(topologies), 4)
        self.assertIn("single_sweep", topologies)
        self.assertIn("hooked_slash", topologies)
        self.assertIn("crescent", topologies)
        self.assertIn("broken_sweep", topologies)
        for candidate in candidates:
            shape = candidate["adapter"]["shape"]
            self.assertGreaterEqual(len(shape["control_points"]), 4)
            self.assertGreaterEqual(len(shape["width_samples"]), 6)
            self.assertTrue(all(len(point) == 3 for point in shape["control_points"]))
            self.assertTrue(all(0.0 <= sample[0] <= 1.0 for sample in shape["width_samples"]))
            self.assertTrue(all(0.0 < sample[1] <= 1.0 for sample in shape["width_samples"]))
            generated_payload = {
                "adapter": candidate["adapter"],
                "layers": candidate["layers"],
                "generation": candidate["generation"],
            }
            self.assertNotIn("V9", json.dumps(generated_payload, ensure_ascii=False))
            self.assertNotIn("V10", json.dumps(generated_payload, ensure_ascii=False))

    def test_writes_run_manifest_and_candidate_specs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root, count=18, seed=42)
            paths = write_run(config)
            manifest = json.loads(paths["run_manifest"].read_text(encoding="utf-8"))
            spec_paths = sorted((config.output_dir / "candidates").glob("*/spec.json"))
            first_spec = json.loads(spec_paths[0].read_text(encoding="utf-8"))

        self.assertEqual(manifest["run_id"], "slash_arc_pref_001_r001")
        self.assertEqual(manifest["candidate_count"], 18)
        self.assertEqual(manifest["generator"], "slash_arc_generator")
        self.assertEqual(manifest["status"], "generated_specs_only")
        self.assertEqual(sum(manifest["topology_counts"].values()), 18)
        self.assertEqual(len(spec_paths), 18)
        self.assertEqual(first_spec["generation"]["run_id"], manifest["run_id"])
        self.assertEqual(first_spec["render_plan"]["time_points_seconds"], [0.30, 0.50, 0.60, 0.75, 0.90])


if __name__ == "__main__":
    unittest.main()
