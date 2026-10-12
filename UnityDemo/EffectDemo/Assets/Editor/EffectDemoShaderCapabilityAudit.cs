using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class EffectDemoShaderCapabilityAudit
{
    private const int AuditRevision = 1;
    private const string MarkerRelativePath = "Library/VFXTraining/shader-capability-audit.marker";
    private const string ReportRelativePath = "Library/VFXTraining/shader-capability-audit.json";

    [Serializable]
    private sealed class AuditReport
    {
        public string schema_version = "effectdemo_shader_capability_audit.v1";
        public string created_at;
        public int audit_revision;
        public string unity_version;
        public string render_pipeline;
        public int shader_count;
        public int supported_shader_count;
        public int shader_error_count;
        public int texture_count;
        public ShaderRecord[] shaders;
        public TextureRecord[] textures;
    }

    [Serializable]
    private sealed class ShaderRecord
    {
        public string shader_name;
        public string shader_path;
        public string shader_guid;
        public string origin;
        public string source_group;
        public string source_extension;
        public bool is_supported;
        public int render_queue;
        public string render_pipeline_tag;
        public string render_type_tag;
        public string[] keywords;
        public string[] dependency_paths;
        public ShaderPropertyRecord[] properties;
        public int error_count;
        public int warning_count;
        public string[] messages;
    }

    [Serializable]
    private sealed class ShaderPropertyRecord
    {
        public string property_name;
        public string property_type;
        public string description;
        public string flags;
    }

    [Serializable]
    private sealed class TextureRecord
    {
        public string texture_path;
        public string texture_guid;
        public string source_group;
        public string source_extension;
        public int width;
        public int height;
        public string texture_format;
        public string texture_type;
        public string alpha_source;
        public bool srgb;
        public string wrap_mode;
        public string filter_mode;
        public int max_texture_size;
        public string compression;
        public bool mipmap_enabled;
        public bool is_readable;
    }

    static EffectDemoShaderCapabilityAudit()
    {
        EditorApplication.delayCall += RunWhenRequested;
    }

    private static void RunWhenRequested()
    {
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var markerPath = Path.Combine(projectRoot, MarkerRelativePath);
        if (!File.Exists(markerPath))
            return;
        File.Delete(markerPath);
        WriteReport(projectRoot, ReportRelativePath);
    }

    public static void RunFromCommandLine()
    {
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var reportPath = CommandLineValue("-shaderCapabilityReport") ?? ReportRelativePath;
        WriteReport(projectRoot, reportPath);
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

    private static void WriteReport(string projectRoot, string reportRelativePath)
    {
        var report = BuildReport();
        var reportPath = Path.IsPathRooted(reportRelativePath) ? reportRelativePath : Path.Combine(projectRoot, reportRelativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(reportPath));
        File.WriteAllText(reportPath, JsonUtility.ToJson(report, true) + "\n");
        Debug.Log($"EffectDemo Shader capability audit completed: {report.shader_count} Shaders, {report.texture_count} Textures, {report.shader_error_count} Shader errors.");
    }

    private static AuditReport BuildReport()
    {
        var shaders = new List<ShaderRecord>();
        foreach (var guid in AssetDatabase.FindAssets("t:Shader"))
        {
            var path = AssetDatabase.GUIDToAssetPath(guid);
            if (string.IsNullOrWhiteSpace(path) || (!path.StartsWith("Assets/", StringComparison.OrdinalIgnoreCase) && !path.StartsWith("Packages/", StringComparison.OrdinalIgnoreCase)))
                continue;
            var shader = AssetDatabase.LoadAssetAtPath<Shader>(path);
            if (shader == null)
                continue;
            var properties = new List<ShaderPropertyRecord>();
            for (var index = 0; index < shader.GetPropertyCount(); index++)
            {
                properties.Add(new ShaderPropertyRecord
                {
                    property_name = shader.GetPropertyName(index),
                    property_type = shader.GetPropertyType(index).ToString().ToLowerInvariant(),
                    description = shader.GetPropertyDescription(index),
                    flags = shader.GetPropertyFlags(index).ToString(),
                });
            }
            var messages = ShaderUtil.GetShaderMessages(shader);
            shaders.Add(new ShaderRecord
            {
                shader_name = shader.name,
                shader_path = path,
                shader_guid = guid,
                origin = path.StartsWith("Assets/", StringComparison.OrdinalIgnoreCase) ? "project_bindable" : path.StartsWith("Packages/com.xuanxuan.nb.fx/", StringComparison.OrdinalIgnoreCase) ? "package_bindable" : "package_reference",
                source_group = SourceGroup(path),
                source_extension = Path.GetExtension(path).ToLowerInvariant(),
                is_supported = shader.isSupported,
                render_queue = shader.renderQueue,
                render_pipeline_tag = string.Empty,
                render_type_tag = string.Empty,
                keywords = shader.keywordSpace.keywords.Select(value => value.name).OrderBy(value => value, StringComparer.Ordinal).ToArray(),
                dependency_paths = AssetDatabase.GetDependencies(path, false).Where(value => !string.Equals(value, path, StringComparison.OrdinalIgnoreCase)).OrderBy(value => value, StringComparer.OrdinalIgnoreCase).ToArray(),
                properties = properties.ToArray(),
                error_count = messages.Count(value => string.Equals(value.severity.ToString(), "Error", StringComparison.OrdinalIgnoreCase)),
                warning_count = messages.Count(value => string.Equals(value.severity.ToString(), "Warning", StringComparison.OrdinalIgnoreCase)),
                messages = messages.Select(value => $"{value.severity}:{value.platform}:{value.file}:{value.line}:{value.message}").ToArray(),
            });
        }

        var textures = new List<TextureRecord>();
        foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { "Assets" }))
        {
            var path = AssetDatabase.GUIDToAssetPath(guid);
            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (texture == null)
                continue;
            var importer = AssetImporter.GetAtPath(path) as TextureImporter;
            textures.Add(new TextureRecord
            {
                texture_path = path,
                texture_guid = guid,
                source_group = SourceGroup(path),
                source_extension = Path.GetExtension(path).ToLowerInvariant(),
                width = texture.width,
                height = texture.height,
                texture_format = texture.format.ToString(),
                texture_type = importer == null ? "unknown" : importer.textureType.ToString(),
                alpha_source = importer == null ? "unknown" : importer.alphaSource.ToString(),
                srgb = importer != null && importer.sRGBTexture,
                wrap_mode = importer == null ? texture.wrapMode.ToString() : importer.wrapMode.ToString(),
                filter_mode = importer == null ? texture.filterMode.ToString() : importer.filterMode.ToString(),
                max_texture_size = importer == null ? 0 : importer.maxTextureSize,
                compression = importer == null ? "unknown" : importer.textureCompression.ToString(),
                mipmap_enabled = importer != null && importer.mipmapEnabled,
                is_readable = importer != null && importer.isReadable,
            });
        }

        var shaderArray = shaders.OrderBy(value => value.shader_path, StringComparer.OrdinalIgnoreCase).ToArray();
        var textureArray = textures.OrderBy(value => value.texture_path, StringComparer.OrdinalIgnoreCase).ToArray();
        return new AuditReport
        {
            created_at = DateTime.UtcNow.ToString("o"),
            audit_revision = AuditRevision,
            unity_version = Application.unityVersion,
            render_pipeline = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline == null ? "not_loaded_no_upm" : UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline.GetType().FullName,
            shader_count = shaderArray.Length,
            supported_shader_count = shaderArray.Count(value => value.is_supported),
            shader_error_count = shaderArray.Sum(value => value.error_count),
            texture_count = textureArray.Length,
            shaders = shaderArray,
            textures = textureArray,
        };
    }

    private static string SourceGroup(string path)
    {
        var parts = (path ?? string.Empty).Replace('\\', '/').Split('/');
        if (parts.Length < 2)
            return "unknown";
        return parts[0] == "Packages" && parts.Length > 1 ? parts[1] : parts[1];
    }
}
