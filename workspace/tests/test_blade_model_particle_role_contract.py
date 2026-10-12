import unittest
from pathlib import Path


class BladeModelParticleRoleContractTests(unittest.TestCase):
    source = Path(
        "E:/UnityVFX/EffectDemo6.0/Assets/Editor/VfxOrangeSlashCommands.cs"
    ).read_text(encoding="utf-8")

    def test_core_and_dark_layers_use_mesh_particles(self):
        self.assertIn("ParticleSystemRenderMode.Mesh", self.source)
        self.assertIn("ConfigureBladeLayer(root.transform.Find(\"CoreBody\")", self.source)
        self.assertIn("ConfigureBladeLayer(root.transform.Find(\"DarkBase\")", self.source)
        self.assertIn("supportMesh", self.source)

    def test_fast_strike_layers_use_point_billboard_particles(self):
        self.assertIn("ParticleSystemRenderMode.Billboard", self.source)
        self.assertIn("ParticleSystemShapeType.SingleSidedEdge", self.source)
        self.assertIn("ConfigureStrikeLayer", self.source)
        self.assertIn("burstCount", self.source)

    def test_static_core_mesh_is_disabled(self):
        self.assertIn("meshRenderer.enabled = false", self.source)


if __name__ == "__main__":
    unittest.main()
