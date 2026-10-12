from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.asset_capability_registry import build_registry


class AssetCapabilityRegistryTests(unittest.TestCase):
    def _jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_merges_texture_content_and_keeps_reference_shaders_non_bindable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "EffectDemo"
            texture = project / "Assets/Pack/Glow.png"
            shader = project / "Assets/Pack/Vfx.shader"
            bad_shader = project / "Assets/Pack/Bad.shader"
            material = project / "Assets/Pack/Vfx.mat"
            bad_material = project / "Assets/Pack/Bad.mat"
            texture.parent.mkdir(parents=True)
            texture.write_bytes(b"texture-content")
            shader.write_text('Shader "Test/Vfx" { Properties { _MainTex("Texture", 2D) = "white" {} } SubShader { Tags { "RenderPipeline"="UniversalPipeline" } } }', encoding="utf-8")
            bad_shader.write_text('Shader "Test/Bad" {}', encoding="utf-8")
            material.write_text("material", encoding="utf-8")
            bad_material.write_text("material", encoding="utf-8")
            texture_sha = hashlib.sha256(texture.read_bytes()).hexdigest()
            shader_audit = root / "shader_audit.json"
            shader_audit.write_text(json.dumps({
                "schema_version": "effectdemo_shader_capability_audit.v1", "unity_version": "2022.3.16f1c1", "render_pipeline": "not_loaded_no_upm",
                "shaders": [
                    {"shader_name": "Test/Vfx", "shader_path": "Assets/Pack/Vfx.shader", "shader_guid": "a" * 32, "is_supported": True, "keywords": [], "dependency_paths": [], "properties": [{"property_name": "_MainTex"}], "error_count": 0, "warning_count": 0, "messages": []},
                    {"shader_name": "Test/Bad", "shader_path": "Assets/Pack/Bad.shader", "shader_guid": "d" * 32, "is_supported": True, "keywords": [], "dependency_paths": [], "properties": [{"property_name": "_MainTex"}], "error_count": 1, "warning_count": 0, "messages": ["Error:test"]},
                ],
                "textures": [{"texture_path": "Assets/Pack/Glow.png", "texture_guid": "b" * 32, "width": 64, "height": 64, "texture_type": "Default", "alpha_source": "FromInput", "srgb": True, "wrap_mode": "Clamp", "filter_mode": "Bilinear", "max_texture_size": 512, "compression": "Uncompressed", "mipmap_enabled": False, "is_readable": False, "texture_format": "RGBA32", "source_extension": ".png", "source_group": "Pack"}],
            }), encoding="utf-8")
            material_audit = root / "material_audit.json"
            material_audit.write_text(json.dumps({
                "schema_version": "effectdemo_material_binding_audit.v4", "unity_version": "2022.3.16f1c1",
                "materials": [
                    {"material_path": "Assets/Pack/Vfx.mat", "material_guid": "c" * 32, "source_group": "Pack", "shader_name": "Test/Vfx", "shader_path": "Assets/Pack/Vfx.shader", "shader_supported": True, "render_queue": 3000, "shader_keywords": [], "properties": [{"property_name": "_MainTex"}], "bindings": [{"property_name": "_MainTex", "is_bound": True, "texture_path": "Assets/Pack/Glow.png"}]},
                    {"material_path": "Assets/Pack/Bad.mat", "material_guid": "e" * 32, "source_group": "Pack", "shader_name": "Test/Bad", "shader_path": "Assets/Pack/Bad.shader", "shader_supported": True, "render_queue": 3000, "shader_keywords": [], "properties": [{"property_name": "_MainTex"}], "bindings": []},
                ],
            }), encoding="utf-8")
            global_texture = root / "global.jsonl"
            self._jsonl(global_texture, [{"asset_id": texture_sha, "relative_path": "Pack/Glow.png", "width": 64, "height": 64, "license_status": "unknown", "tags": ["semantic.spark", "slot.alpha_mask"]}])
            reference_texture = root / "resource/Pack/Glow.png"
            reference_texture.parent.mkdir(parents=True)
            reference_texture.write_bytes(b"texture-content")
            github = root / "github/Repo"
            github.mkdir(parents=True)
            (github / "LICENSE").write_text("MIT License", encoding="utf-8")
            (github / "Ref.shader").write_text('Shader "Ref/Only" { Properties { _Mask("Mask", 2D) = "white" {} } }', encoding="utf-8")
            nb = root / "nb"
            nb.mkdir()
            (nb / "NB.shader").write_text('Shader "Effects/NBShader" {}', encoding="utf-8")
            paths = build_registry(shader_audit, material_audit, global_texture, project, github.parent, nb, root / "output", "test_registry")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            textures = [json.loads(line) for line in paths["textures"].read_text(encoding="utf-8").splitlines()]
            shaders = [json.loads(line) for line in paths["shaders"].read_text(encoding="utf-8").splitlines()]
            materials = [json.loads(line) for line in paths["materials"].read_text(encoding="utf-8").splitlines()]

        merged = next(row for row in textures if row["content_sha256"] == texture_sha)
        self.assertEqual(merged["binding_status"], "project_bindable")
        self.assertIn("semantic.spark", merged["tags"])
        self.assertIsInstance(merged["metrics"], dict)
        self.assertEqual(len(merged["source_paths"]), 2)
        self.assertEqual(sum(row["source_kind"] == "github_reference" for row in shaders), 1)
        self.assertEqual(sum(row["source_kind"] == "package_reference" for row in shaders), 1)
        self.assertTrue(all(row["binding_status"] == "reference_only" for row in shaders if row["source_kind"] != "project_bindable"))
        usable = next(row for row in materials if row["shader_name"] == "Test/Vfx")
        blocked = next(row for row in materials if row["shader_name"] == "Test/Bad")
        self.assertEqual(usable["binding_status"], "usable")
        self.assertIsNotNone(usable["texture_bindings"][0]["texture_asset_id"])
        self.assertEqual(blocked["binding_status"], "blocked_shader")
        self.assertEqual(set(manifest["quality_gates"].values()), {0})

    def test_unity_audit_contract_covers_all_assets_and_shader_capabilities(self) -> None:
        material_source = Path("UnityDemo/EffectDemo/Assets/Editor/EffectDemoMaterialBindingAudit.cs").read_text(encoding="utf-8")
        shader_source = Path("UnityDemo/EffectDemo/Assets/Editor/EffectDemoShaderCapabilityAudit.cs").read_text(encoding="utf-8")
        self.assertIn('WriteReport(projectRoot, "Assets", FullAssetReportRelativePath)', material_source)
        self.assertIn("material.shaderKeywords", material_source)
        self.assertIn('AssetDatabase.FindAssets("t:Shader")', shader_source)
        self.assertIn('AssetDatabase.FindAssets("t:Texture2D", new[] { "Assets" })', shader_source)
        self.assertIn("ShaderUtil.GetShaderMessages", shader_source)


if __name__ == "__main__":
    unittest.main()
