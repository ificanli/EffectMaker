import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.slash_arc_texture_profile import TextureSelectionConfig, build_slash_arc_texture_profile


class SlashArcTextureProfileTests(unittest.TestCase):
    def test_builds_material_slot_profile_from_tagged_textures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tags = root / "tags.jsonl"
            rows = [
                {
                    "asset_id": "base-1",
                    "relative_path": "Slash/Base.png",
                    "width": 512,
                    "height": 512,
                    "license_status": "unknown",
                    "thumbnail_status": "thumb/base.png",
                    "tags": ["semantic.slash", "slot.base_map", "role.core_shape", "alpha.sparse", "luma.bright_core"],
                    "metrics": {"bright_ratio": 0.2, "alpha_std": 0.4},
                },
                {
                    "asset_id": "noise-1",
                    "relative_path": "Noise/Dissolve.png",
                    "width": 256,
                    "height": 256,
                    "license_status": "unknown",
                    "thumbnail_status": "thumb/noise.png",
                    "tags": ["semantic.noise", "slot.dissolve_map", "slot.distortion_map", "role.noise_control", "motion.dissolve_reveal", "shape.square"],
                    "metrics": {"luminance_std": 0.3},
                },
                {
                    "asset_id": "ramp-1",
                    "relative_path": "Gradient/Ramp.png",
                    "width": 256,
                    "height": 32,
                    "license_status": "unknown",
                    "thumbnail_status": "thumb/ramp.png",
                    "tags": ["semantic.gradient", "slot.ramp_map", "role.color_control", "shape.horizontal_strip"],
                    "metrics": {},
                },
            ]
            tags.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            output = root / "profile.json"

            profile = build_slash_arc_texture_profile(TextureSelectionConfig(tag_files=(tags,), output=output))

            self.assertTrue(output.is_file())

        self.assertEqual(profile["schema_version"], "slash_arc_texture_profile.v1")
        self.assertEqual(profile["shader"]["name"], "Universal Render Pipeline/Particles/Unlit")
        self.assertEqual(profile["shader_candidates"][0]["name"], "Universal Render Pipeline/Particles/Unlit")
        self.assertEqual(profile["material_selection"]["shader_name"], "Universal Render Pipeline/Particles/Unlit")
        self.assertEqual(profile["material_selection"]["slot_rules"]["base_map"]["required_tags"], ["semantic.slash", "slot.base_map"])
        self.assertEqual(profile["slots"]["base_map"][0]["asset_id"], "base-1")
        self.assertEqual(profile["slots"]["dissolve_map"][0]["asset_id"], "noise-1")
        self.assertEqual(profile["slots"]["ramp_map"][0]["asset_id"], "ramp-1")


if __name__ == "__main__":
    unittest.main()
