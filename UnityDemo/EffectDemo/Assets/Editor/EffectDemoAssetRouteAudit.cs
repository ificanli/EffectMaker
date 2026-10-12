using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class EffectDemoAssetRouteAudit
{
    [Serializable]
    private sealed class Request
    {
        public string output_path;
        public string[] mesh_paths;
        public string[] material_paths;
    }

    [Serializable]
    private sealed class MeshRecord
    {
        public string asset_path;
        public string mesh_name;
        public string status;
        public int vertex_count;
        public int sub_mesh_count;
        public int uv_count;
        public bool uv_valid;
        public string axis_space;
        public string pivot_mode;
        public float[] bounds_center;
        public float[] bounds_size;
    }

    [Serializable]
    private sealed class MaterialRecord
    {
        public string asset_path;
        public string status;
        public string shader_name;
        public bool has_main_texture;
    }

    [Serializable]
    private sealed class Result
    {
        public string schema_version = "vfx_prefab_asset_route_audit.v1";
        public string created_at;
        public List<MeshRecord> meshes = new List<MeshRecord>();
        public List<MaterialRecord> materials = new List<MaterialRecord>();
    }

    public static void Run()
    {
        var requestPath = GetArgument("-assetRouteAuditRequest");
        if (string.IsNullOrWhiteSpace(requestPath))
        {
            throw new InvalidOperationException("-assetRouteAuditRequest is required");
        }

        var request = JsonUtility.FromJson<Request>(File.ReadAllText(requestPath));
        var result = new Result { created_at = DateTime.UtcNow.ToString("o") };
        foreach (var assetPath in request.mesh_paths ?? Array.Empty<string>())
        {
            AuditMeshes(assetPath, result.meshes);
        }
        foreach (var assetPath in request.material_paths ?? Array.Empty<string>())
        {
            AuditMaterial(assetPath, result.materials);
        }
        var parent = Path.GetDirectoryName(request.output_path);
        if (!string.IsNullOrWhiteSpace(parent)) Directory.CreateDirectory(parent);
        File.WriteAllText(request.output_path, JsonUtility.ToJson(result, true));
        AssetDatabase.SaveAssets();
    }

    private static void AuditMeshes(string assetPath, List<MeshRecord> output)
    {
        var assets = AssetDatabase.LoadAllAssetsAtPath(assetPath);
        foreach (var asset in assets)
        {
            var mesh = asset as Mesh;
            if (mesh == null) continue;
            var uvCount = mesh.uv == null ? 0 : mesh.uv.Length;
            var valid = mesh.vertexCount > 0 && mesh.subMeshCount > 0 && uvCount == mesh.vertexCount;
            output.Add(new MeshRecord
            {
                asset_path = assetPath,
                mesh_name = mesh.name,
                status = valid ? "pass" : "blocked",
                vertex_count = mesh.vertexCount,
                sub_mesh_count = mesh.subMeshCount,
                uv_count = uvCount,
                uv_valid = uvCount == mesh.vertexCount,
                axis_space = "unity_local",
                pivot_mode = "source_import_pivot",
                bounds_center = new[] { mesh.bounds.center.x, mesh.bounds.center.y, mesh.bounds.center.z },
                bounds_size = new[] { mesh.bounds.size.x, mesh.bounds.size.y, mesh.bounds.size.z },
            });
        }
    }

    private static void AuditMaterial(string assetPath, List<MaterialRecord> output)
    {
        var material = AssetDatabase.LoadAssetAtPath<Material>(assetPath);
        var shaderName = material == null || material.shader == null ? null : material.shader.name;
        output.Add(new MaterialRecord
        {
            asset_path = assetPath,
            status = material != null && material.shader != null ? "pass" : "blocked",
            shader_name = shaderName,
            has_main_texture = material != null && material.HasProperty("_MainTex") && material.GetTexture("_MainTex") != null,
        });
    }

    private static string GetArgument(string name)
    {
        var arguments = Environment.GetCommandLineArgs();
        for (var index = 0; index + 1 < arguments.Length; index++)
        {
            if (arguments[index] == name) return arguments[index + 1];
        }
        return null;
    }
}
