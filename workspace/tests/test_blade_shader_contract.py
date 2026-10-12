import os
import unittest
from pathlib import Path


DEFAULT_PROJECT = Path("E:/UnityVFX/EffectDemo6.0")


class BladeShaderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(os.environ.get("UNITY_VFX_PROJECT", DEFAULT_PROJECT))
        cls.shader_path = (
            project
            / "Assets"
            / "Art"
            / "VFX"
            / "BladeReproduction"
            / "Shaders"
            / "BladeSurface.shader"
        )
        cls.source = cls.shader_path.read_text(encoding="utf-8")

    def test_material_controls_source_and_destination_blend(self):
        self.assertIn("_SrcBlend", self.source)
        self.assertIn("Blend [_SrcBlend] [_DstBlend]", self.source)

    def test_particle_custom_data_offsets_flow_uv(self):
        self.assertIn("input.customData.xy", self.source)
        self.assertIn("float2 flow", self.source)

    def test_texture_color_can_be_disabled_for_alpha_only_impact_tint(self):
        self.assertIn("_TextureColorStrength", self.source)
        self.assertIn("textureColor", self.source)
        self.assertIn("lerp(half3(1.0h, 1.0h, 1.0h)", self.source)

    def test_directional_coordinate_drives_dissolve(self):
        self.assertIn("_DissolveDirection", self.source)
        self.assertIn("directionCoordinate", self.source)
        self.assertIn("directionCoordinate + dissolve", self.source)

    def test_tip_fade_uses_mesh_uv_endpoint(self):
        self.assertIn("_TipFadeWidth", self.source)
        self.assertIn("input.uv.x", self.source)
        self.assertIn("tipFade", self.source)

    def test_length_fade_uses_both_mesh_uv_endpoints(self):
        self.assertIn("_LengthFadeWidth", self.source)
        self.assertIn("startFade", self.source)
        self.assertIn("endFade", self.source)

    def test_core_band_uses_cross_mesh_uv(self):
        self.assertIn("_CoreBandStrength", self.source)
        self.assertIn("_CoreBandWidth", self.source)
        self.assertIn("centerDistance", self.source)
        self.assertIn("input.uv.y", self.source)


if __name__ == "__main__":
    unittest.main()
