from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class PrefabGraphReadbackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabGraphReadback.cs").read_text(encoding="utf-8")

    def test_readback_uses_asset_database_and_unity_component_api(self) -> None:
        self.assertIn("AssetDatabase.LoadAssetAtPath<GameObject>", self.source)
        self.assertIn("GetComponent<ParticleSystem>()", self.source)
        self.assertIn("GetComponent<ParticleSystemRenderer>()", self.source)
        self.assertIn("GetAssetPath", self.source)
        self.assertNotIn("ReadAllText(prefabPath)", self.source)
        self.assertIn("source_prefab_instantiated = false", self.source)

    def test_readback_compares_transforms_parameters_and_renderer(self) -> None:
        self.assertIn("CompareNode", self.source)
        self.assertIn("CompareParticle", self.source)
        self.assertIn("renderer_type:", self.source)
        self.assertIn("NormalizeEmpty(input.parent_node_id)", self.source)
        self.assertIn('renderer_type = renderer.GetType().Name', self.source)
        self.assertIn("the optional condition object", self.source)
        self.assertIn("left.shape_enabled &&", self.source)
        self.assertIn("serializes the root null parent", self.source)
        self.assertIn("material replaces template binding", self.source)
        self.assertIn("start_delay_max = main.startDelay.constantMax", self.source)
        self.assertIn("start_rotation_max = main.startRotation.constantMax", self.source)
        self.assertIn("gravity_modifier_max = main.gravityModifier.constantMax", self.source)
        self.assertIn("start_size_3d = main.startSize3D", self.source)
        self.assertIn("start_size_x_max = main.startSizeX.constantMax", self.source)
        self.assertIn("start_size_max = main.startSize.constantMax", self.source)
        self.assertIn("!left.start_size_3d && !Close(left.start_size_max, right.start_size_max)", self.source)
        self.assertIn("ActiveVertexStreams(renderer)", self.source)
        self.assertIn("active_vertex_streams differ", self.source)
        self.assertIn("active_vertex_streams.SequenceEqual", self.source)
        self.assertIn("Close(left.start_delay_max, right.start_delay_max)", self.source)
        self.assertIn('differences.Add($"particle[{nodeId}].mesh_paths differ")', self.source)
        self.assertIn('differences.Add($"renderer[{nodeId}].mesh_paths differ")', self.source)

    def test_powershell_entrypoint_is_no_upm_capable(self) -> None:
        source = (ROOT / "workspace/tools/effectdemo_readback_prefab_graph.ps1").read_text(encoding="utf-8")
        self.assertIn("EffectDemoPrefabGraphReadback.ReadbackFromCommandLine", source)
        self.assertIn('if ($NoUpm)', source)


if __name__ == "__main__":
    unittest.main()
