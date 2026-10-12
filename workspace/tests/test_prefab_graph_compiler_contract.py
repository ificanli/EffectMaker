from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class PrefabGraphCompilerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabGraphCompiler.cs").read_text(encoding="utf-8")

    def test_compiler_uses_unity_api_and_never_instantiates_source_prefab(self) -> None:
        self.assertIn("PrefabUtility.SaveAsPrefabAsset", self.source)
        self.assertIn("source_prefab_read = false", self.source)
        self.assertIn("new GameObject(node.name, typeof(ParticleSystem))", self.source)
        self.assertIn("ParticleSystem node was not constructed with its native component", self.source)
        self.assertNotIn("PrefabUtility.InstantiatePrefab", self.source)
        self.assertNotIn("target.AddComponent<ParticleSystem>()", self.source)
        self.assertNotIn("File.WriteAllText(outputPrefabPath", self.source)

    def test_compiler_rejects_incomplete_graphs_and_parent_prefab(self) -> None:
        self.assertIn('graph.reconstruction.status != "reconstructable"', self.source)
        self.assertIn('graph.reconstruction.compiler_profile != "particle_v1"', self.source)
        self.assertIn("No-parent compiler smoke rejects parent_prefab_path", self.source)

    def test_compiler_requires_real_asset_resolution(self) -> None:
        self.assertIn("AssetDatabase.LoadAssetAtPath<Material>", self.source)
        self.assertIn("Particle material could not be loaded", self.source)
        self.assertIn("AssetDatabase.CreateAsset", self.source)
        self.assertIn("CreateParticleTexture", self.source)
        self.assertIn('generated.SetTexture("_BaseMap", texture)', self.source)
        self.assertIn("ConfigureTransparentParticleMaterial", self.source)
        self.assertIn('material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT")', self.source)
        self.assertIn('material.EnableKeyword("_ALPHABLEND_ON")', self.source)
        self.assertIn('material.SetFloat("_DstBlend", (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha)', self.source)

    def test_generated_shader_requires_explicit_profile_and_default_template_is_supported(self) -> None:
        shader = (ROOT / "UnityDemo/EffectDemo/Assets/VFXGenerated/PrefabGraph/Shaders/PrefabGraphSoftParticle.shader").read_text(encoding="utf-8")
        self.assertIn('Shader "VFXGenerated/SoftParticle"', shader)
        self.assertIn("Blend SrcAlpha OneMinusSrcAlpha", shader)
        self.assertIn("ZWrite Off", shader)
        self.assertIn('"LightMode"="UniversalForward"', shader)
        self.assertNotIn('"RenderPipeline"="UniversalPipeline"', shader)
        self.assertIn("return tex2D(_MainTex, input.uv) * _Color;", shader)
        self.assertIn('component.parameters?.shader_profile, "generated_soft"', self.source)
        self.assertIn("var defaultParticleMaterial = renderer.sharedMaterial", self.source)
        self.assertIn("new Material(defaultParticleMaterial)", self.source)
        self.assertIn("Particle material template could not be loaded", self.source)
        self.assertIn("new Material(materialTemplate)", self.source)
        self.assertIn("IsBuiltinAssetPath", self.source)
        self.assertIn("projectMaterialPaths", self.source)

    def test_material_plan_binds_real_project_texture_and_reports_it(self) -> None:
        self.assertIn("texture_asset_path", self.source)
        self.assertIn("texture_property_name", self.source)
        self.assertIn("AssetDatabase.LoadAssetAtPath<Texture>(textureAssetPath)", self.source)
        self.assertIn("generated.SetTexture(propertyName, texture)", self.source)
        self.assertIn("bound_texture_paths", self.source)
        self.assertIn("CaptureMaterialTextureReadbacks", self.source)
        self.assertIn("planned_texture_readback_match", self.source)
        self.assertIn("boundTextures.All(readbackTexturePaths.Contains)", self.source)

    def test_compiler_supports_layer_timing_rotation_and_gravity(self) -> None:
        self.assertIn("main.startDelay = Mathf.Max(0f, parameters.start_delay_max)", self.source)
        self.assertIn("main.startRotation = parameters.start_rotation_max", self.source)
        self.assertIn("main.gravityModifier = parameters.gravity_modifier_max", self.source)

    def test_compiler_supports_nonuniform_particle_size_and_vertex_stream_contracts(self) -> None:
        self.assertIn("main.startSize3D = parameters.start_size_3d", self.source)
        self.assertIn("main.startSizeX = Mathf.Max(0.001f, parameters.start_size_x_max)", self.source)
        self.assertIn("main.startSizeY = Mathf.Max(0.001f, parameters.start_size_y_max)", self.source)
        self.assertIn("ConfigureActiveVertexStreams", self.source)
        self.assertIn("renderer.SetActiveVertexStreams(streams)", self.source)
        self.assertIn("Unsupported ParticleSystemVertexStream", self.source)

    def test_compiler_binds_real_mesh_for_mesh_particles(self) -> None:
        self.assertIn("renderer.renderMode == ParticleSystemRenderMode.Mesh", self.source)
        self.assertIn("renderer.mesh = LoadFirstMesh(meshPaths[0])", self.source)
        self.assertIn("AssetDatabase.LoadAllAssetsAtPath(assetPath).OfType<Mesh>().FirstOrDefault()", self.source)
        self.assertIn('generated.HasProperty("_TintColor")', self.source)


if __name__ == "__main__":
    unittest.main()
