import unittest
from pathlib import Path


class BladeLayerStructureContractTests(unittest.TestCase):
    source = Path(
        "E:/UnityVFX/EffectDemo6.0/Assets/Editor/VfxOrangeSlashCommands.cs"
    ).read_text(encoding="utf-8")

    def test_all_reproduction_layers_use_candidate_mesh_rendering(self):
        self.assertIn("ParticleSystemRenderMode.Mesh", self.source)
        self.assertIn("coreMesh", self.source)
        self.assertIn("supportMesh", self.source)
        self.assertIn("CoreMesh", self.source)

    def test_static_core_renderer_is_disabled_before_dynamic_layers(self):
        self.assertIn("meshRenderer.enabled = false", self.source)

    def test_support_and_strike_layers_have_explicit_offsets(self):
        self.assertIn("localPosition", self.source)
        self.assertIn("DarkBase", self.source)
        self.assertIn("FastStrike_A", self.source)
        self.assertIn("FastStrike_B", self.source)


if __name__ == "__main__":
    unittest.main()
