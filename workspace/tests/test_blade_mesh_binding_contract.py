import unittest
from pathlib import Path


class BladeMeshBindingContractTests(unittest.TestCase):
    source = Path(
        "E:/UnityVFX/EffectDemo6.0/Assets/Editor/VfxOrangeSlashCommands.cs"
    ).read_text(encoding="utf-8")

    def test_core_body_binds_candidate_mesh_and_renderer(self):
        self.assertIn("SlashArc_BiTaper_ContinuousUV.obj", self.source)
        self.assertIn("SlashArc_Support_ContinuousUV.obj", self.source)
        self.assertIn("MeshFilter", self.source)
        self.assertIn("MeshRenderer", self.source)
        self.assertIn("CoreBody_Mat.mat", self.source)


if __name__ == "__main__":
    unittest.main()
