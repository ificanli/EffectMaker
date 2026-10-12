using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class EffectDemoParticleColorCalibration
{
    private const string Folder = "Assets/Generated/ParticleColorCalibrationAssetsR001";
    private const string Template = Folder + "/NeutralUrpParticles.mat";

    [Serializable] private sealed class Manifest { public Case[] cases; }
    [Serializable] private sealed class Case { public string case_id; public string prefab_path; }
    [Serializable] private sealed class ColorProperty { public string name; public float[] rgba; }
    [Serializable] private sealed class GradientSample { public float time; public float[] rgba; }
    [Serializable] private sealed class ParticleAudit
    {
        public string name;
        public float[] start_color;
        public EffectDemoParticleColorGradient lifetime;
        public float[] initial_vertex_color_product;
        public string shader;
        public string material;
        public ColorProperty[] material_colors;
        public string[] vertex_streams;
        public GradientSample[] lifetime_samples;
    }
    [Serializable] private sealed class CaseAudit { public string case_id; public ParticleAudit[] particles; }
    [Serializable] private sealed class Report { public string unity_version; public string color_space; public CaseAudit[] cases; }

    public static void PrepareAndCompile()
    {
        EnsureFolder(Folder);
        var template = AssetDatabase.LoadAssetAtPath<Material>(Template);
        if (template == null)
        {
            var original = AssetDatabase.LoadAssetAtPath<Material>("Packages/com.unity.render-pipelines.universal/Runtime/Materials/ParticlesUnlit.mat");
            if (original == null) throw new InvalidOperationException("Official URP particle template is unavailable.");
            template = new Material(original) { name = "NeutralUrpParticles" };
            template.SetColor("_BaseColor", Color.white);
            template.SetTexture("_BaseMap", Texture2D.whiteTexture);
            template.SetColor("_EmissionColor", Color.black);
            template.DisableKeyword("_EMISSION");
            AssetDatabase.CreateAsset(template, Template);
            AssetDatabase.SaveAssets();
        }
        if (template.shader.name != "Universal Render Pipeline/Particles/Unlit" || template.GetColor("_BaseColor") != Color.white)
            throw new InvalidOperationException("Calibration material was changed; refusing to overwrite it.");
        EffectDemoPrefabGraphCompiler.CompileBatchFromCommandLine();
    }

    public static void AuditFromCommandLine()
    {
        var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Argument("-colorCalibrationManifest")));
        var cases = new List<CaseAudit>();
        foreach (var item in manifest.cases)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(item.prefab_path);
            if (prefab == null) throw new FileNotFoundException(item.prefab_path);
            var particles = new List<ParticleAudit>();
            foreach (var system in prefab.GetComponentsInChildren<ParticleSystem>(true))
            {
                var renderer = system.GetComponent<ParticleSystemRenderer>();
                var material = renderer.sharedMaterial;
                var streams = new List<ParticleSystemVertexStream>();
                renderer.GetActiveVertexStreams(streams);
                var start = system.main.startColor.color;
                var lifetime = system.colorOverLifetime;
                var colorProperties = new List<ColorProperty>();
                for (var index = 0; index < material.shader.GetPropertyCount(); index++)
                {
                    if (material.shader.GetPropertyType(index) != UnityEngine.Rendering.ShaderPropertyType.Color) continue;
                    var name = material.shader.GetPropertyName(index);
                    colorProperties.Add(new ColorProperty { name = name, rgba = Values(material.GetColor(name)) });
                }
                particles.Add(new ParticleAudit
                {
                    name = system.name, start_color = Values(start),
                    lifetime = lifetime.enabled ? EffectDemoParticleColorGradient.FromUnity(lifetime.color) : null,
                    initial_vertex_color_product = Values(start * (lifetime.enabled ? lifetime.color.Evaluate(0f) : Color.white)),
                    shader = material.shader.name, material = AssetDatabase.GetAssetPath(material),
                    material_colors = colorProperties.ToArray(), vertex_streams = streams.Select(value => value.ToString()).ToArray(),
                    lifetime_samples = new[] { 0f, 0.1f, 0.25f, 0.5f, 0.8f, 1f }.Select(time => new GradientSample { time = time, rgba = Values(lifetime.enabled ? lifetime.color.Evaluate(time) : Color.white) }).ToArray(),
                });
            }
            cases.Add(new CaseAudit { case_id = item.case_id, particles = particles.ToArray() });
        }
        var report = new Report { unity_version = Application.unityVersion, color_space = QualitySettings.activeColorSpace.ToString(), cases = cases.ToArray() };
        File.WriteAllText(Argument("-colorCalibrationAudit"), JsonUtility.ToJson(report, true) + "\n");
    }

    public static void CreateRandomStartColorNegative()
    {
        var source = AssetDatabase.LoadAssetAtPath<GameObject>(Argument("-randomColorSource"));
        var output = Argument("-randomColorOutput");
        if (source == null || AssetDatabase.LoadAssetAtPath<GameObject>(output) != null)
            throw new InvalidOperationException("Missing source or existing random-color negative output.");
        EnsureFolder(Path.GetDirectoryName(output).Replace('\\', '/'));
        var instance = (GameObject)PrefabUtility.InstantiatePrefab(source);
        try
        {
            PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            instance.name = source.name;
            var particle = instance.GetComponentInChildren<ParticleSystem>(true);
            var main = particle.main;
            var expectedMaximum = main.startColor.color;
            main.startColor = new ParticleSystem.MinMaxGradient(Color.black, expectedMaximum);
            PrefabUtility.SaveAsPrefabAsset(instance, output);
            AssetDatabase.SaveAssets();
            if (AssetDatabase.LoadAssetAtPath<GameObject>(output).GetComponentInChildren<ParticleSystem>(true).main.startColor.mode != ParticleSystemGradientMode.TwoColors)
                throw new InvalidOperationException("Random Start Color negative did not persist.");
        }
        finally { UnityEngine.Object.DestroyImmediate(instance); }
    }

    private static float[] Values(Color value) => new[] { value.r, value.g, value.b, value.a };
    private static string Argument(string key)
    {
        var args = Environment.GetCommandLineArgs();
        var index = Array.IndexOf(args, key);
        if (index < 0 || index + 1 == args.Length) throw new ArgumentException("Missing " + key);
        return args[index + 1];
    }
    private static void EnsureFolder(string path)
    {
        if (AssetDatabase.IsValidFolder(path)) return;
        var parent = Path.GetDirectoryName(path).Replace('\\', '/');
        EnsureFolder(parent);
        AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
    }
}
