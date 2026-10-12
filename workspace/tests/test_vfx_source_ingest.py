import hashlib
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from workspace.tools.vfx_source_ingest import IngestConfig, build_source_ingest, load_or_build_guid_map, read_meta_guid


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_png(
    path: Path,
    size: tuple[int, int] = (16, 16),
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(path)


class VfxSourceIngestTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "SourceProject"
        (project / "Assets").mkdir(parents=True)
        (project / "ProjectSettings").mkdir()
        (project / "Packages").mkdir()
        write(project / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.56f1c1\n")
        write(
            project / "Packages" / "manifest.json",
            json.dumps({"dependencies": {"com.unity.render-pipelines.universal": "14.0.0"}}),
        )
        return project

    def test_builds_manifest_sample_spec_and_training_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "Hit"
            prefab = sample / "Hit.prefab"
            mat = sample / "Hit.mat"
            shader = sample / "Hit.shader"
            tex = sample / "Hit.png"
            write(prefab, "ParticleSystem:\nParticleSystem:\nParticleSystemRenderer:\n  m_Materials:\n  - {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n")
            write(prefab.with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            write(mat, "m_Shader: {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n- {fileID: 2800000, guid: dddddddddddddddddddddddddddddddd, type: 3}\n")
            write(mat.with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            write(shader, "Shader \"Test/Hit\" {}\n")
            write(shader.with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            tex.write_bytes(b"png")
            write(tex.with_suffix(".png.meta"), "guid: dddddddddddddddddddddddddddddddd\n")
            tag_index = root / "texture_tags.jsonl"
            texture_relative_path = "Assets/Effects/Hit/Hit.png"
            tag_index.write_text(
                json.dumps(
                    {
                        "schema_version": "texture_tags.v1",
                        "asset_id": hashlib.sha256(texture_relative_path.encode("utf-8")).hexdigest(),
                        "relative_path": texture_relative_path,
                        "extension": ".png",
                        "width": 16,
                        "height": 16,
                        "license_status": "unknown",
                        "thumbnail_status": "thumb/hit.png",
                        "tags": [
                            "semantic.slash",
                            "slot.base_map",
                            "role.core_shape",
                            "alpha.sparse",
                            "luma.bright_core",
                        ],
                        "metrics": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            out = root / "out"
            paths = build_source_ingest(
                IngestConfig(
                    source_path=sample,
                    output_dir=out,
                    source_id="SRC-TEST-HIT-001",
                    title="Hit test",
                    effect_family="hit",
                    source_unity_project=project,
                    beads_id="vfx-test",
                    texture_tag_index_path=tag_index,
                )
            )
            manifest = json.loads(paths["source_manifest"].read_text(encoding="utf-8"))
            sample_doc = json.loads(paths["source_sample"].read_text(encoding="utf-8"))
            spec = json.loads(paths["derived_vfxspec"].read_text(encoding="utf-8"))
            training = json.loads(paths["training_example"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["unity_context"]["unity_version"], "2022.3.56f1c1")
        self.assertEqual(manifest["unity_context"]["pipeline_version"], "14.0.0")
        self.assertEqual(len([f for f in manifest["files"] if f["role"] == "prefab"]), 1)
        self.assertEqual(len(manifest["dependencies"]), 3)
        self.assertTrue(all(dep["status"] == "resolved" for dep in manifest["dependencies"]))
        self.assertEqual(sample_doc["extracted"]["component_summary"]["particle_systems"], 2)
        self.assertEqual(sample_doc["extracted"]["material_selection"]["shader_candidates"][0]["path"], "Assets/Effects/Hit/Hit.shader")
        self.assertEqual(sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["path"], "Assets/Effects/Hit/Hit.png")
        self.assertEqual(sample_doc["extracted"]["material_selection"]["texture_tag_index_status"], "loaded")
        self.assertEqual(sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["tag_match"], "asset_id")
        self.assertIn("semantic.slash", sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["tags"])
        self.assertIn("base_map", sample_doc["extracted"]["material_selection"]["materials"][0]["slot_role_hints"])
        self.assertEqual(sample_doc["extracted"]["material_selection"]["materials"][0]["primary_shader_path"], "Assets/Effects/Hit/Hit.shader")
        self.assertEqual(sample_doc["extracted"]["material_selection"]["texture_tag_index_path"], tag_index.as_posix())
        self.assertIn("material_selection", spec["layers"][0]["material_parameters"])
        self.assertEqual(spec["generation"]["candidate_id"], "src-test-hit-001_candidate_001")
        self.assertEqual(training["inputs"]["source_manifest_path"], "source_manifest.json")
        self.assertIn("material_selection", training["inputs"])
        self.assertEqual(training["inputs"]["material_selection"]["material_count"], 1)
        self.assertEqual(training["inputs"]["material_selection"]["texture_tagging_status"], "required_for_slot_selection")
        self.assertIn("semantic.slash", training["inputs"]["material_selection"]["texture_candidates"][0]["tags"])

    def test_builds_local_texture_tag_index_when_none_is_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "Slash"
            prefab = sample / "Slash.prefab"
            mat = sample / "Slash.mat"
            shader = sample / "Slash.shader"
            tex = sample / "SlashMask.png"
            write(
                prefab,
                "ParticleSystem:\nParticleSystemRenderer:\n  m_Materials:\n  - {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n",
            )
            write(prefab.with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            write(
                mat,
                "m_Shader: {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n"
                "m_SavedProperties:\n"
                "  m_TexEnvs:\n"
                "  - _MainTex: {fileID: 2800000, guid: dddddddddddddddddddddddddddddddd, type: 3}\n",
            )
            write(mat.with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            write(shader, 'Shader "Test/Slash" {}\n')
            write(shader.with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            write_png(tex)
            write(tex.with_suffix(".png.meta"), "guid: dddddddddddddddddddddddddddddddd\n")

            out = root / "out"
            paths = build_source_ingest(
                IngestConfig(
                    source_path=sample,
                    output_dir=out,
                    source_id="SRC-TEST-SLASH-LOCAL",
                    title="Slash local tag index test",
                    effect_family="slash",
                    source_unity_project=project,
                    beads_id="vfx-test",
                )
            )
            manifest = json.loads(paths["source_manifest"].read_text(encoding="utf-8"))
            sample_doc = json.loads(paths["source_sample"].read_text(encoding="utf-8"))
            training = json.loads(paths["training_example"].read_text(encoding="utf-8"))
            local_tag_index = out / "texture_tags.jsonl"
            self.assertTrue(local_tag_index.exists())
            self.assertEqual(manifest["extraction"]["texture_tag_index_source"], "generated_local")
            self.assertEqual(manifest["extraction"]["texture_tag_index_status"], "loaded")
            self.assertEqual(manifest["extraction"]["texture_tag_index_record_count"], 1)
            self.assertEqual(manifest["extraction"]["texture_tag_index_path"], local_tag_index.as_posix())
            self.assertEqual(sample_doc["extracted"]["material_selection"]["texture_tag_index_path"], local_tag_index.as_posix())
            self.assertEqual(sample_doc["extracted"]["material_selection"]["texture_tag_index_status"], "loaded")
            self.assertEqual(sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["tag_match"], "asset_id")
            self.assertIn("semantic.slash", sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["tags"])
            self.assertIn("semantic.mask", sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["tags"])
            self.assertIn("base_map", sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["slot_roles"])
            self.assertIn("alpha_mask", sample_doc["extracted"]["material_selection"]["texture_candidates"][0]["slot_roles"])
            self.assertIn("base_map", sample_doc["extracted"]["material_selection"]["materials"][0]["slot_role_hints"])
            self.assertIn("alpha_mask", sample_doc["extracted"]["material_selection"]["materials"][0]["slot_role_hints"])
            self.assertEqual(training["inputs"]["material_selection"]["texture_tag_index_path"], local_tag_index.as_posix())
            self.assertIn("semantic.slash", training["inputs"]["material_selection"]["texture_candidates"][0]["tags"])
            self.assertIn("semantic.mask", training["inputs"]["material_selection"]["texture_candidates"][0]["tags"])

    def test_copy_assets_into_target_project_without_deleting_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            source = project / "Assets" / "Effects" / "Small"
            prefab = source / "Small.prefab"
            write(prefab, "ParticleSystem:\n")
            write(prefab.with_suffix(".prefab.meta"), "guid: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\n")
            write(Path(str(source) + ".meta"), "guid: ffffffffffffffffffffffffffffffff\n")
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))

            paths = build_source_ingest(
                IngestConfig(
                    source_path=source,
                    output_dir=root / "out",
                    source_id="SRC-COPY-001",
                    title="Copy test",
                    effect_family="slash",
                    source_unity_project=project,
                    target_unity_project=target,
                    copy_assets=True,
                    copy_name="CopiedSmall",
                )
            )
            manifest = json.loads(paths["source_manifest"].read_text(encoding="utf-8"))

            self.assertTrue((target / "Assets" / "VFXSourceIngest" / "Trains" / "CopiedSmall" / "Small.prefab").exists())
            self.assertTrue((target / "Assets" / "VFXSourceIngest" / "Trains" / "CopiedSmall.meta").exists())
            self.assertTrue(prefab.exists())
            self.assertEqual(manifest["root"]["relative_to"], "target_unity_project")
            self.assertEqual(manifest["unity_context"]["original_project_path"], project.resolve().as_posix())

    def test_copy_dependency_closure_copies_material_texture_mesh_and_shader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            prefab_dir = project / "Assets" / "ArtResources" / "IgnoreEffectPrefab"
            shared_dir = project / "Assets" / "ArtResources" / "FX" / "Shared"
            prefab = prefab_dir / "Hit.prefab"
            material = shared_dir / "Hit.mat"
            shader = shared_dir / "Hit.shader"
            texture = shared_dir / "Hit.png"
            mesh = shared_dir / "Hit.fbx"
            script = project / "Assets" / "Scripts" / "HitBehaviour.cs"
            write(
                prefab,
                "\n".join(
                    [
                        "ParticleSystem:",
                        "ParticleSystemRenderer:",
                        "  m_Materials:",
                        "  - {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}",
                        "  m_Mesh: {fileID: 4300000, guid: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee, type: 3}",
                        "MonoBehaviour:",
                        "  m_Script: {fileID: 11500000, guid: ffffffffffffffffffffffffffffffff, type: 3}",
                    ]
                )
                + "\n",
            )
            write(prefab.with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            write(
                material,
                "m_Shader: {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n"
                "- {fileID: 2800000, guid: dddddddddddddddddddddddddddddddd, type: 3}\n",
            )
            write(material.with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            write(shader, "Shader \"Test/Hit\" {}\n")
            write(shader.with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            texture.write_bytes(b"png")
            write(texture.with_suffix(".png.meta"), "guid: dddddddddddddddddddddddddddddddd\n")
            mesh.write_bytes(b"fbx")
            write(mesh.with_suffix(".fbx.meta"), "guid: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\n")
            write(script, "public class HitBehaviour {}\n")
            write(script.with_suffix(".cs.meta"), "guid: ffffffffffffffffffffffffffffffff\n")
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))

            paths = build_source_ingest(
                IngestConfig(
                    source_path=prefab_dir,
                    output_dir=root / "out",
                    source_id="SRC-CLOSURE-001",
                    title="Closure copy test",
                    effect_family="hit",
                    source_unity_project=project,
                    target_unity_project=target,
                    copy_assets=True,
                    copy_dependency_closure=True,
                    copy_name="ClosureCopy",
                    resolve_project_guids=True,
                )
            )
            manifest = json.loads(paths["source_manifest"].read_text(encoding="utf-8"))
            summary = json.loads(paths["source_sample"].read_text(encoding="utf-8"))["extracted"]["component_summary"]

            copied_root = target / "Assets" / "VFXSourceIngest" / "Trains" / "ClosureCopy"
            self.assertTrue((copied_root / "ArtResources" / "IgnoreEffectPrefab" / "Hit.prefab").exists())
            self.assertTrue((copied_root / "ArtResources" / "FX" / "Shared" / "Hit.mat").exists())
            self.assertTrue((copied_root / "ArtResources" / "FX" / "Shared" / "Hit.shader").exists())
            self.assertTrue((copied_root / "ArtResources" / "FX" / "Shared" / "Hit.png").exists())
            self.assertTrue((copied_root / "ArtResources" / "FX" / "Shared" / "Hit.fbx").exists())
            self.assertFalse((copied_root / "Scripts" / "HitBehaviour.cs").exists())
            self.assertGreaterEqual(summary["material"], 1)
            self.assertGreaterEqual(summary["texture"], 1)
            self.assertGreaterEqual(summary["mesh"], 1)
            self.assertGreaterEqual(summary["shader"], 1)
            self.assertEqual(summary["external_dependencies"], 0)
            self.assertEqual(summary["ignored_dependencies"], 1)
            self.assertIn("Assets/VFXSourceIngest/Trains/ClosureCopy/ArtResources/FX/Shared/Hit.mat", [f["path"] for f in manifest["files"]])

    def test_copy_dependency_closure_copies_local_shader_includes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            source = project / "Assets" / "Bundles" / "Shaders"
            shader_dir = source / "Common"
            library_dir = source / "ShaderLibraries"
            shader = shader_dir / "Sample.shader"
            include = library_dir / "SharedCommon.hlsl"
            write(include, "float4 SharedColor(float4 c) { return c; }\n")
            write(include.with_suffix(".hlsl.meta"), "guid: 11111111111111111111111111111111\n")
            write(
                shader,
                "\n".join(
                    [
                        'Shader "Test/Sample"',
                        "{",
                        "SubShader",
                        "{",
                        "Pass",
                        "{",
                        "HLSLPROGRAM",
                        '#include "../ShaderLibraries/SharedCommon.hlsl"',
                        "ENDHLSL",
                        "}",
                        "}",
                        "}",
                    ]
                )
                + "\n",
            )
            write(Path(str(shader) + ".meta"), "guid: 22222222222222222222222222222222\n")
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))

            paths = build_source_ingest(
                IngestConfig(
                    source_path=shader_dir,
                    output_dir=root / "out",
                    source_id="SRC-SHADER-INCLUDE-001",
                    title="Shader include test",
                    effect_family="mixed",
                    source_unity_project=project,
                    target_unity_project=target,
                    copy_assets=True,
                    copy_dependency_closure=True,
                    copy_name="ShaderCopy",
                    resolve_project_guids=True,
                )
            )
            manifest = json.loads(paths["source_manifest"].read_text(encoding="utf-8"))
            copied_root = target / "Assets" / "VFXSourceIngest" / "Trains" / "ShaderCopy"

            self.assertTrue((copied_root / "Bundles" / "Shaders" / "Common" / "Sample.shader").exists())
            self.assertTrue((copied_root / "Bundles" / "Shaders" / "ShaderLibraries" / "SharedCommon.hlsl").exists())
            self.assertTrue((copied_root / "Bundles" / "Shaders" / "Common" / "Sample.shader.meta").exists())
            self.assertEqual(
                (copied_root / "Bundles" / "Shaders" / "Common" / "Sample.shader.meta").read_text(encoding="utf-8"),
                "guid: 22222222222222222222222222222222\n",
            )
            self.assertGreaterEqual(len([f for f in manifest["files"] if f["role"] == "shader"]), 1)
            self.assertGreaterEqual(len([f for f in manifest["files"] if f["role"] == "shader_include"]), 1)

    def test_guid_map_cache_hits_then_rebuilds_after_meta_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            asset = project / "Assets" / "Vfx" / "Sample.prefab"
            write(asset, "ParticleSystem:\n")
            write(asset.with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            cache = root / "cache" / "guid_map.json"

            first_map, first_summary = load_or_build_guid_map(project / "Assets", project, cache)
            second_map, second_summary = load_or_build_guid_map(project / "Assets", project, cache)
            time.sleep(0.002)
            write(asset.with_suffix(".prefab.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            third_map, third_summary = load_or_build_guid_map(project / "Assets", project, cache)

        self.assertEqual(first_summary["status"], "rebuilt")
        self.assertEqual(second_summary["status"], "cache_hit")
        self.assertEqual(third_summary["status"], "rebuilt")
        self.assertIn("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", first_map)
        self.assertIn("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", second_map)
        self.assertIn("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", third_map)

    def test_shared_dependency_pool_reuses_shader_texture_and_rewrites_guids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            source_root = project / "Assets" / "Effects"
            shared = project / "Assets" / "Shared"
            shader = shared / "Vfx.shader"
            texture = shared / "Vfx.png"
            material = shared / "Vfx.mat"
            write(shader, 'Shader "Test/Vfx" {}\n')
            write(shader.with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            texture.write_bytes(b"same-texture")
            write(texture.with_suffix(".png.meta"), "guid: dddddddddddddddddddddddddddddddd\n")
            write(
                material,
                "m_Shader: {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n"
                "- {fileID: 2800000, guid: dddddddddddddddddddddddddddddddd, type: 3}\n",
            )
            write(material.with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))

            for sample_name, prefab_guid in (("One", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ("Two", "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")):
                sample = source_root / sample_name
                write(
                    sample / "Effect.prefab",
                    "ParticleSystem:\n"
                    "- {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n",
                )
                write((sample / "Effect.prefab").with_suffix(".prefab.meta"), f"guid: {prefab_guid}\n")

            common = dict(
                output_dir=root / "out",
                effect_family="mixed",
                source_unity_project=project,
                target_unity_project=target,
                copy_assets=True,
                copy_dependency_closure=True,
                resolve_project_guids=True,
                shared_dependency_store="Assets/VFXSourceIngest/Shared",
                dedupe_by="sha256",
                rewrite_guid_references=True,
            )
            build_source_ingest(IngestConfig(source_path=source_root / "One", source_id="SRC-SHARED-ONE", title="Shared one", copy_name="SampleOne", **common))
            paths = build_source_ingest(IngestConfig(source_path=source_root / "Two", source_id="SRC-SHARED-TWO", title="Shared two", copy_name="SampleTwo", **common))
            index = json.loads((target / "Library" / "VFXSourceIngest" / "shared_dependency_index.json").read_text(encoding="utf-8"))
            report = json.loads((root / "out" / "shared_dependency_report.json").read_text(encoding="utf-8"))
            copied_prefabs = list((target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleTwo").rglob("Effect.prefab"))
            copied_materials = list((target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleTwo").rglob("Vfx.mat"))
            shared_shaders = list((target / "Assets" / "VFXSourceIngest" / "Shared" / "ShaderPackages" / "Shared").rglob("*.shader"))
            shared_textures = list((target / "Assets" / "VFXSourceIngest" / "Shared" / "Textures").rglob("*.png"))
            shader_text = shared_shaders[0].read_text(encoding="utf-8")
            self.assertEqual(len(copied_materials), 1)
            self.assertEqual(len(copied_prefabs), 1)
            copied_prefab_text = copied_prefabs[0].read_text(encoding="utf-8")
            copied_material_text = copied_materials[0].read_text(encoding="utf-8")
            copied_material_guid = read_meta_guid(copied_materials[0].with_suffix(".mat.meta"))
            manifest = json.loads(paths["source_manifest"].read_text(encoding="utf-8"))
            summary = json.loads(paths["source_sample"].read_text(encoding="utf-8"))["extracted"]["component_summary"]
            manifest_dedupe_by = manifest["extraction"]["dedupe_by"]
            shared_dependency_count = sum(1 for dep in manifest["dependencies"] if dep["status"] == "resolved_shared")
            resolved_shared_count = summary["resolved_shared_dependencies"]
            index_in_assets_exists = (target / "Assets" / "VFXSourceIngest" / "Shared" / "dependency_index.json").exists()
            report_in_assets_exists = (target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleTwo" / "shared_dependency_report.json").exists()

        self.assertEqual(len(index["assets"]), 2)
        self.assertEqual(report["reused_shared"], 2)
        self.assertEqual(len(shared_shaders), 1)
        self.assertEqual(shared_shaders[0].parent.name, "Shared")
        self.assertIn('Shader "Test/Vfx"', shader_text)
        self.assertEqual(len(shared_textures), 1)
        self.assertFalse(index_in_assets_exists)
        self.assertFalse(report_in_assets_exists)
        self.assertEqual(report["integrity"]["status"], "passed")
        self.assertIn("guid:", copied_prefab_text)
        self.assertNotEqual(copied_material_guid, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        self.assertIn(copied_material_guid, copied_prefab_text)
        self.assertNotIn("cccccccccccccccccccccccccccccccc", copied_material_text)
        self.assertNotIn("dddddddddddddddddddddddddddddddd", copied_material_text)
        self.assertEqual(manifest_dedupe_by, "sha256")
        self.assertGreaterEqual(shared_dependency_count, 2)
        self.assertGreaterEqual(resolved_shared_count, 2)

    def test_shared_pool_rebases_material_guids_per_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            shared = project / "Assets" / "Shared"
            shader = shared / "Vfx.shader"
            texture = shared / "Vfx.png"
            material = shared / "Vfx.mat"
            write(shader, 'Shader "Test/Vfx" {}\n')
            write(shader.with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            texture.write_bytes(b"same-texture")
            write(texture.with_suffix(".png.meta"), "guid: dddddddddddddddddddddddddddddddd\n")
            write(material, "m_Shader: {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n- {fileID: 2800000, guid: dddddddddddddddddddddddddddddddd, type: 3}\n")
            write(material.with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))
            source_root = project / "Assets" / "Effects"
            for name, prefab_guid in (("One", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ("Two", "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")):
                prefab = source_root / name / "Effect.prefab"
                write(prefab, "- {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n")
                write(prefab.with_suffix(".prefab.meta"), f"guid: {prefab_guid}\n")
            common = dict(
                output_dir=root / "out",
                effect_family="mixed",
                source_unity_project=project,
                target_unity_project=target,
                copy_assets=True,
                copy_dependency_closure=True,
                resolve_project_guids=True,
                shared_dependency_store="Assets/VFXSourceIngest/Shared",
                dedupe_by="sha256",
                rewrite_guid_references=True,
            )
            build_source_ingest(IngestConfig(source_path=source_root / "One", source_id="SRC-MAT-ONE", title="one", copy_name="SampleOne", **common))
            build_source_ingest(IngestConfig(source_path=source_root / "Two", source_id="SRC-MAT-TWO", title="two", copy_name="SampleTwo", **common))
            one_material = next((target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleOne").rglob("Vfx.mat"))
            two_material = next((target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleTwo").rglob("Vfx.mat"))
            one_prefab = next((target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleOne").rglob("Effect.prefab"))
            two_prefab = next((target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleTwo").rglob("Effect.prefab"))
            one_guid = read_meta_guid(one_material.with_suffix(".mat.meta"))
            two_guid = read_meta_guid(two_material.with_suffix(".mat.meta"))
            one_text = one_prefab.read_text(encoding="utf-8")
            two_text = two_prefab.read_text(encoding="utf-8")

        self.assertNotEqual(one_guid, two_guid)
        self.assertNotEqual(one_guid, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        self.assertNotEqual(two_guid, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        self.assertIn(one_guid, one_text)
        self.assertIn(two_guid, two_text)

    def test_rebased_shared_texture_preserves_source_importer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "Sample"
            texture = project / "Assets" / "Textures" / "Mask.png"
            write(sample / "Effect.prefab", "- {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n")
            write((sample / "Effect.prefab").with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            write(sample / "Effect.mat", "- {fileID: 2800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n")
            write((sample / "Effect.mat").with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            texture.parent.mkdir(parents=True, exist_ok=True)
            texture.write_bytes(b"texture")
            write(
                texture.with_suffix(".png.meta"),
                "fileFormatVersion: 2\n"
                "guid: cccccccccccccccccccccccccccccccc\n"
                "TextureImporter:\n"
                "  textureType: 1\n",
            )
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))
            build_source_ingest(IngestConfig(
                source_path=sample,
                output_dir=root / "out",
                source_id="SRC-IMPORTER-META",
                title="importer meta",
                effect_family="mixed",
                source_unity_project=project,
                target_unity_project=target,
                copy_assets=True,
                copy_dependency_closure=True,
                resolve_project_guids=True,
                copy_name="Sample",
                shared_dependency_store="Assets/VFXSourceIngest/Shared",
                dedupe_by="sha256",
                rewrite_guid_references=True,
            ))
            copied_texture_meta = next((target / "Assets" / "VFXSourceIngest" / "Shared" / "Textures").rglob("Mask_*.png.meta"))
            copied_meta_text = copied_texture_meta.read_text(encoding="utf-8")

        self.assertIn("TextureImporter:", copied_meta_text)
        self.assertNotIn("guid: cccccccccccccccccccccccccccccccc", copied_meta_text)

    def test_shared_index_rebuild_and_folder_metas_do_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            shared = project / "Assets" / "Shared"
            shader = shared / "Vfx.shader"
            texture = shared / "Vfx.png"
            material = shared / "Vfx.mat"
            write(shader, 'Shader "Test/Vfx" {}\n')
            write(shader.with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            texture.write_bytes(b"same-texture")
            write(texture.with_suffix(".png.meta"), "guid: dddddddddddddddddddddddddddddddd\n")
            write(material, "m_Shader: {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n")
            write(material.with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))
            sample_root = project / "Assets" / "Effects"
            for name, guid in (("One", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ("Two", "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")):
                sample = sample_root / name
                write(sample / "Effect.prefab", "- {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n")
                write((sample / "Effect.prefab").with_suffix(".prefab.meta"), f"guid: {guid}\n")
            common = dict(
                output_dir=root / "out",
                effect_family="mixed",
                source_unity_project=project,
                target_unity_project=target,
                copy_assets=True,
                copy_dependency_closure=True,
                resolve_project_guids=True,
                shared_dependency_store="Assets/VFXSourceIngest/Shared",
                dedupe_by="sha256",
                rewrite_guid_references=True,
            )
            build_source_ingest(IngestConfig(source_path=sample_root / "One", source_id="SRC-REBUILD-ONE", title="one", copy_name="SampleOne", **common))
            index_path = target / "Library" / "VFXSourceIngest" / "shared_dependency_index.json"
            index_path.unlink()
            build_source_ingest(IngestConfig(source_path=sample_root / "Two", source_id="SRC-REBUILD-TWO", title="two", copy_name="SampleTwo", **common))
            first_folder_meta = target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleOne" / "Effects.meta"
            second_folder_meta = target / "Assets" / "VFXSourceIngest" / "Trains" / "SampleTwo" / "Effects.meta"
            index_rebuilt = index_path.exists()
            first_folder_guid = read_meta_guid(first_folder_meta)
            second_folder_guid = read_meta_guid(second_folder_meta)

        self.assertTrue(index_rebuilt)
        self.assertNotEqual(first_folder_guid, second_folder_guid)

    def test_shared_dependency_pool_dry_run_does_not_create_target_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "Preview"
            shader = project / "Assets" / "Shared" / "Preview.shader"
            write(shader, 'Shader "Test/Preview" {}\n')
            write(shader.with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            write(sample / "Preview.prefab", "- {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n")
            write((sample / "Preview.prefab").with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            target = root / "TargetProject"
            (target / "Assets").mkdir(parents=True)
            (target / "ProjectSettings").mkdir()
            (target / "Packages").mkdir()
            write(target / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.16f1c1\n")
            write(target / "Packages" / "manifest.json", json.dumps({"dependencies": {}}))
            out = root / "out"

            build_source_ingest(IngestConfig(
                source_path=sample,
                output_dir=out,
                source_id="SRC-SHARED-DRY",
                title="Shared dry run",
                effect_family="mixed",
                source_unity_project=project,
                target_unity_project=target,
                copy_assets=True,
                copy_dependency_closure=True,
                resolve_project_guids=True,
                copy_name="DrySample",
                shared_dependency_store="Assets/VFXSourceIngest/Shared",
                dedupe_by="sha256",
                rewrite_guid_references=True,
                dry_run=True,
            ))

            self.assertFalse((target / "Assets" / "VFXSourceIngest").exists())
            report = json.loads((out / "shared_dependency_dry_run.json").read_text(encoding="utf-8"))

        self.assertTrue(report["dry_run"])
        self.assertGreaterEqual(report["guid_rewrite_count"], 1)

    def test_integrity_gate_rejects_unresolved_material_texture_guid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "BrokenTexture"
            write(sample / "Effect.prefab", "- {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n")
            write((sample / "Effect.prefab").with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            write(
                sample / "Effect.mat",
                "m_SavedProperties:\n"
                "  m_TexEnvs:\n"
                "  - _MainTex:\n"
                "      m_Texture: {fileID: 2800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n",
            )
            write((sample / "Effect.mat").with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            output = root / "out"

            with self.assertRaisesRegex(ValueError, "ingest integrity gate failed"):
                build_source_ingest(IngestConfig(
                    source_path=sample,
                    output_dir=output,
                    source_id="SRC-BROKEN-TEXTURE",
                    title="broken texture",
                    effect_family="mixed",
                    source_unity_project=project,
                ))
            report = json.loads((output / "ingest_integrity_report.json").read_text(encoding="utf-8"))
            manifest = json.loads((output / "source_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(report["material_integrity"]["gate"]["status"], "failed")
        self.assertEqual(report["material_integrity"]["m_texture_slot_status_counts"]["missing"], 1)
        self.assertEqual(manifest["ingest_status"], "blocked")

    def test_integrity_audits_material_referenced_outside_selected_source_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "ExternalMaterial"
            shared = project / "Assets" / "Shared"
            write(
                sample / "Effect.prefab",
                "- {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n"
                "MonoBehaviour:\n  m_Script: {fileID: 11500000, guid: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee, type: 3}\n",
            )
            write((sample / "Effect.prefab").with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            write(
                shared / "Effect.mat",
                "m_SavedProperties:\n  m_TexEnvs:\n  - _MainTex:\n"
                "      m_Texture: {fileID: 2800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n",
            )
            write((shared / "Effect.mat").with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            write_png(shared / "Effect.png")
            write((shared / "Effect.png").with_suffix(".png.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            write(project / "Assets" / "Scripts" / "EffectDriver.cs", "public class EffectDriver {}\n")
            write((project / "Assets" / "Scripts" / "EffectDriver.cs").with_suffix(".cs.meta"), "guid: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\n")

            paths = build_source_ingest(IngestConfig(
                source_path=sample,
                output_dir=root / "out",
                source_id="SRC-EXTERNAL-MATERIAL",
                title="external material",
                effect_family="mixed",
                source_unity_project=project,
                resolve_project_guids=True,
            ))
            report = json.loads(paths["ingest_integrity_report"].read_text(encoding="utf-8"))

        self.assertEqual(report["material_integrity"]["material_count"], 1)
        self.assertEqual(report["material_integrity"]["m_texture_slot_status_counts"]["resolved"], 1)
        self.assertEqual(report["material_integrity"]["gate"]["status"], "passed")
        self.assertEqual(report["material_integrity"]["guid_reference_summary"]["dependency_type_counts"]["script"], 1)

    def test_rejects_missing_source_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            with self.assertRaisesRegex(FileNotFoundError, "source path does not exist"):
                build_source_ingest(IngestConfig(
                    source_path=project / "Assets" / "DoesNotExist",
                    output_dir=root / "out",
                    source_id="SRC-MISSING-PATH",
                    title="missing path",
                    effect_family="mixed",
                    source_unity_project=project,
                ))

    def test_integrity_gate_rejects_duplicate_material_guids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "DuplicateMaterial"
            write(sample / "Effect.prefab", "ParticleSystem:\n")
            write((sample / "Effect.prefab").with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            for name in ("One.mat", "Two.mat"):
                material = project / "Assets" / "Materials" / name
                write(material, "m_SavedProperties:\n  m_TexEnvs: []\n")
                write(material.with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            output = root / "out"

            with self.assertRaisesRegex(ValueError, "duplicate material GUID"):
                build_source_ingest(IngestConfig(
                    source_path=sample,
                    output_dir=output,
                    source_id="SRC-DUPLICATE-MATERIAL",
                    title="duplicate material",
                    effect_family="mixed",
                    source_unity_project=project,
                ))
            report = json.loads((output / "ingest_integrity_report.json").read_text(encoding="utf-8"))

        self.assertEqual(len(report["material_integrity"]["material_guid_duplicates"]), 1)
        self.assertEqual(report["material_integrity"]["gate"]["status"], "failed")

    def test_shader_custom_editor_policy_copies_explicitly_allowed_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.make_project(root)
            sample = project / "Assets" / "Effects" / "CustomEditor"
            write(sample / "Effect.prefab", "- {fileID: 2100000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}\n")
            write((sample / "Effect.prefab").with_suffix(".prefab.meta"), "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
            write(
                sample / "Effect.mat",
                "m_Shader: {fileID: 4800000, guid: cccccccccccccccccccccccccccccccc, type: 3}\n"
                "m_SavedProperties:\n  m_TexEnvs:\n  - _MainTex:\n"
                "      m_Texture: {fileID: 2800000, guid: dddddddddddddddddddddddddddddddd, type: 3}\n",
            )
            write((sample / "Effect.mat").with_suffix(".mat.meta"), "guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            write(
                sample / "Effect.shader",
                'Shader "Test/Custom"\n{\n    CustomEditor "Example.Editor.CustomGui"\n}\n',
            )
            write((sample / "Effect.shader").with_suffix(".shader.meta"), "guid: cccccccccccccccccccccccccccccccc\n")
            write_png(sample / "Effect.png")
            write((sample / "Effect.png").with_suffix(".png.meta"), "guid: dddddddddddddddddddddddddddddddd\n")
            source_gui = project / "Assets" / "Editor" / "ExampleGui"
            write(source_gui / "CustomGui.cs", "namespace Example.Editor { public class CustomGui {} }\n")
            write((source_gui / "CustomGui.cs").with_suffix(".cs.meta"), "guid: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\n")
            write(Path(str(source_gui) + ".meta"), "guid: ffffffffffffffffffffffffffffffff\n")
            target = self.make_project(root / "Target")
            policy = root / "shader_gui_policy.json"
            policy.write_text(json.dumps({
                "schema_version": "vfx_shader_gui_policy.v1",
                "dependencies": {
                    "Example.Editor.CustomGui": {
                        "allowed": True,
                        "license_status": "local_reference_only",
                        "source_path": "Assets/Editor/ExampleGui",
                        "target_path": "Assets/Editor/ExampleGui",
                    }
                },
            }), encoding="utf-8")

            paths = build_source_ingest(IngestConfig(
                source_path=sample,
                output_dir=root / "out",
                source_id="SRC-CUSTOM-EDITOR",
                title="custom editor",
                effect_family="mixed",
                source_unity_project=project,
                target_unity_project=target,
                copy_assets=True,
                copy_name="CustomEditor",
                shader_gui_policy_path=policy,
                copy_shader_gui_dependencies=True,
            ))
            report = json.loads(paths["ingest_integrity_report"].read_text(encoding="utf-8"))
            copied_shader_gui_exists = (target / "Assets" / "Editor" / "ExampleGui" / "CustomGui.cs").is_file()

        record = report["shader_custom_editor"]["records"][0]
        self.assertEqual(record["custom_editor"], "Example.Editor.CustomGui")
        self.assertEqual(record["target_status"], "copied_allowed")
        self.assertEqual(record["copy_action"]["action"], "copied")
        self.assertTrue(copied_shader_gui_exists)



if __name__ == "__main__":
    unittest.main()
