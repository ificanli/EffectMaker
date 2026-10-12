using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

[InitializeOnLoad]
public static class EffectDemoMaterialBindingAudit
{
    // Bump this revision when an importer repair needs a fresh Editor-side binding audit.
    private const int AuditRevision = 4;
    private const string MarkerRelativePath = "Library/VFXSourceIngest/material-binding-audit.marker";
    private const string ReportRelativePath = "Library/VFXSourceIngest/material-binding-audit.json";
    private const string FullAssetMarkerRelativePath = "Library/VFXTraining/full-material-binding-audit.marker";
    private const string FullAssetReportRelativePath = "Library/VFXTraining/full-material-binding-audit.json";

    [Serializable]
    private sealed class AuditReport
    {
        public string schema_version = "effectdemo_material_binding_audit.v4";
        public string created_at;
        public int audit_revision;
        public string unity_version;
        public string scan_root;
        public MaterialRecord[] materials;
        public int material_count;
        public int texture_slot_count;
        public int bound_texture_slot_count;
        public int unbound_texture_slot_count;
        public int shader_property_count;
    }

    [Serializable]
    private sealed class MaterialRecord
    {
        public string material_path;
        public string material_guid;
        public string source_group;
        public string shader_name;
        public string shader_path;
        public string shader_guid;
        public bool shader_supported;
        public int render_queue;
        public string[] shader_keywords;
        public int texture_slot_count;
        public int bound_texture_slot_count;
        public string[] unbound_slots;
        public TextureBinding[] bindings;
        public ShaderProperty[] properties;
    }

    [Serializable]
    private sealed class TextureBinding
    {
        public string property_name;
        public bool is_bound;
        public string texture_name;
        public string texture_path;
        public string texture_guid;
        public int width;
        public int height;
    }

    [Serializable]
    private sealed class ShaderProperty
    {
        public string property_name;
        public string property_type;
    }

    static EffectDemoMaterialBindingAudit()
    {
        EditorApplication.delayCall += RunWhenRequested;
    }

    private static void RunWhenRequested()
    {
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var markerPath = Path.Combine(projectRoot, MarkerRelativePath);
        if (File.Exists(markerPath))
        {
            File.Delete(markerPath);
            WriteReport(projectRoot, "Assets/VFXSourceIngest", ReportRelativePath);
        }

        var fullAssetMarkerPath = Path.Combine(projectRoot, FullAssetMarkerRelativePath);
        if (File.Exists(fullAssetMarkerPath))
        {
            File.Delete(fullAssetMarkerPath);
            WriteReport(projectRoot, "Assets", FullAssetReportRelativePath);
        }
    }

    public static void RunFromCommandLine()
    {
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var scanRoot = CommandLineValue("-materialAuditRoot") ?? "Assets/VFXSourceIngest";
        var reportPath = CommandLineValue("-materialAuditReport") ?? ReportRelativePath;
        WriteReport(projectRoot, scanRoot, reportPath);
    }

    private static string CommandLineValue(string name)
    {
        var arguments = Environment.GetCommandLineArgs();
        for (var index = 0; index < arguments.Length - 1; index++)
        {
            if (string.Equals(arguments[index], name, StringComparison.OrdinalIgnoreCase))
                return arguments[index + 1];
        }
        return null;
    }

    private static void WriteReport(string projectRoot, string scanRoot, string reportRelativePath)
    {
        var report = BuildReport(scanRoot);
        var reportPath = Path.IsPathRooted(reportRelativePath) ? reportRelativePath : Path.Combine(projectRoot, reportRelativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(reportPath));
        File.WriteAllText(reportPath, JsonUtility.ToJson(report, true) + "\n");
        Debug.Log($"EffectDemo material binding audit r{AuditRevision} completed: {report.material_count} materials, {report.bound_texture_slot_count}/{report.texture_slot_count} texture slots bound.");
    }

    private static AuditReport BuildReport(string scanRoot)
    {
        var records = new List<MaterialRecord>();
        var textureSlotCount = 0;
        var boundTextureSlotCount = 0;
        var shaderPropertyCount = 0;
        foreach (var guid in AssetDatabase.FindAssets("t:Material", new[] { scanRoot }))
        {
            var materialPath = AssetDatabase.GUIDToAssetPath(guid);
            var material = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
            if (material == null)
                continue;
            var bindings = new List<TextureBinding>();
            var unboundSlots = new List<string>();
            var properties = new List<ShaderProperty>();
            if (material.shader != null)
            {
                for (var propertyIndex = 0; propertyIndex < material.shader.GetPropertyCount(); propertyIndex++)
                {
                    properties.Add(new ShaderProperty
                    {
                        property_name = material.shader.GetPropertyName(propertyIndex),
                        property_type = material.shader.GetPropertyType(propertyIndex).ToString().ToLowerInvariant(),
                    });
                    shaderPropertyCount++;
                }
            }
            foreach (var propertyName in material.GetTexturePropertyNames())
            {
                var texture = material.GetTexture(propertyName);
                var isBound = texture != null;
                textureSlotCount++;
                if (isBound)
                    boundTextureSlotCount++;
                else
                    unboundSlots.Add(propertyName);
                bindings.Add(new TextureBinding
                {
                    property_name = propertyName,
                    is_bound = isBound,
                    texture_name = texture == null ? null : texture.name,
                    texture_path = texture == null ? null : AssetDatabase.GetAssetPath(texture),
                    texture_guid = texture == null ? null : AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(texture)),
                    width = texture == null ? 0 : texture.width,
                    height = texture == null ? 0 : texture.height,
                });
            }
            var shaderPath = material.shader == null ? null : AssetDatabase.GetAssetPath(material.shader);
            records.Add(new MaterialRecord
            {
                material_path = materialPath,
                material_guid = guid,
                source_group = SourceGroup(materialPath),
                shader_name = material.shader == null ? null : material.shader.name,
                shader_path = shaderPath,
                shader_guid = string.IsNullOrWhiteSpace(shaderPath) ? null : AssetDatabase.AssetPathToGUID(shaderPath),
                shader_supported = material.shader != null && material.shader.isSupported,
                render_queue = material.renderQueue,
                shader_keywords = material.shaderKeywords.OrderBy(value => value, StringComparer.Ordinal).ToArray(),
                texture_slot_count = bindings.Count,
                bound_texture_slot_count = bindings.FindAll(binding => binding.is_bound).Count,
                unbound_slots = unboundSlots.ToArray(),
                bindings = bindings.ToArray(),
                properties = properties.ToArray(),
            });
        }
        return new AuditReport
        {
            audit_revision = AuditRevision,
            unity_version = Application.unityVersion,
            scan_root = scanRoot,
            created_at = DateTime.UtcNow.ToString("o"),
            material_count = records.Count,
            texture_slot_count = textureSlotCount,
            bound_texture_slot_count = boundTextureSlotCount,
            unbound_texture_slot_count = textureSlotCount - boundTextureSlotCount,
            shader_property_count = shaderPropertyCount,
            materials = records.OrderBy(value => value.material_path, StringComparer.OrdinalIgnoreCase).ToArray(),
        };
    }

    private static string SourceGroup(string path)
    {
        var parts = (path ?? string.Empty).Replace('\\', '/').Split('/');
        return parts.Length > 1 ? parts[1] : "unknown";
    }
}
