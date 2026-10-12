using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class EffectDemoPrefabGraphSourceExporter
{
    private const string GraphSchemaVersion = "vfx_prefab_graph.v1";
    private const string RequestSchemaVersion = "vfx_prefab_graph_source_export_requests.v1";

    [Serializable]
    private sealed class RequestManifest { public string schema_version; public string source_dataset_id; public string source_cases_path; public SourceRequest[] requests; }
    [Serializable]
    private sealed class SourceRequest { public string candidate_id; public string prefab_path; public string graph_path; public string report_path; }

    [Serializable]
    private sealed class Graph
    {
        public string schema_version;
        public string graph_id;
        public Source source;
        public string root_node_id;
        public Node[] nodes;
        public Components components;
        public AssetBindings asset_bindings;
        public Reconstruction reconstruction;
        public Training training;
        public Provenance provenance;
    }

    [Serializable] private sealed class Source { public string source_kind; public string prefab_path; public string source_example_id; }
    [Serializable] private sealed class Node
    {
        public string node_id; public string name; public string role; public int sibling_index; public int depth; public string parent_node_id; public string hierarchy_path; public bool active_self; public string[] component_types; public TransformData transform;
    }
    [Serializable] private sealed class TransformData { public float[] local_position; public float[] local_rotation; public float[] local_scale; }
    [Serializable] private sealed class Components { public ParticleComponent[] particle_systems; public RendererComponent[] renderers; public AnimationComponent[] animations; }
    [Serializable] private sealed class ParticleComponent { public string component_id; public string node_id; public ParticleParameters parameters; public string[] material_paths; public string[] mesh_paths; }
    [Serializable]
    private sealed class ParticleParameters
    {
        public EffectDemoParticleColorGradient color_over_lifetime_gradient;
        public string material_color_mode;
        public float duration_seconds; public float start_delay_max; public bool looping; public string simulation_space; public int max_particles; public float start_lifetime_max; public float start_speed_max; public float start_size_max; public bool start_size_3d; public float start_size_x_max; public float start_size_y_max; public float start_size_z_max; public float start_rotation_max; public float gravity_modifier_max; public float[] start_color_rgba; public float[] end_color_rgba; public bool emission_enabled; public float emission_rate_over_time_max; public int burst_particle_count; public bool shape_enabled; public string shape_type; public float shape_radius; public bool color_over_lifetime_enabled; public bool size_over_lifetime_enabled; public float end_size_multiplier; public string renderer_mode; public int sorting_order; public string texture_profile; public string shader_profile; public string material_template_path; public ModuleSnapshot serialized_modules;
    }
    [Serializable] private sealed class ModuleSnapshot { public bool emission; public bool shape; public bool color_over_lifetime; public bool size_over_lifetime; public bool rotation_over_lifetime; public bool texture_sheet_animation; public bool velocity_over_lifetime; public bool custom_data; }
    [Serializable] private sealed class RendererComponent { public string component_id; public string node_id; public string renderer_type; public bool enabled; public RendererParameters parameters; public string[] material_paths; public string[] mesh_paths; }
    [Serializable] private sealed class RendererParameters { public string particle_render_mode; public int sorting_order; public string[] active_vertex_streams; }
    [Serializable] private sealed class AnimationComponent { public string component_id; public string node_id; public string animation_type; public AnimationParameters parameters; }
    [Serializable] private sealed class AnimationParameters { public int clip_count; public float duration_seconds; }
    [Serializable] private sealed class AssetBindings { public string[] materials; public string[] meshes; }
    [Serializable] private sealed class Reconstruction { public string status; public string compiler_profile; public string[] missing_fields; public string[] unsupported_components; }
    [Serializable] private sealed class Training { public string[] eligible_tasks; public string[] excluded_tasks; public string aesthetic_label_source; }
    [Serializable] private sealed class Provenance { public string source_dataset_id; public string source_run_id; public string exporter; public string[] assumptions; }

    [Serializable]
    private sealed class ExportReport
    {
        public string schema_version = "vfx_prefab_graph_source_export_report.v1"; public string created_at; public string candidate_id; public string prefab_path; public string graph_path; public string status; public string reconstruction_status; public int node_count; public int particle_system_count; public int renderer_count; public int animation_count; public string[] material_paths; public string[] mesh_paths; public string[] missing_fields; public string[] unsupported_components; public string error;
    }

    public static void ExportFromCommandLine()
    {
        var requestPath = CommandLineValue("-prefabGraphSourceRequests");
        if (string.IsNullOrWhiteSpace(requestPath) || !File.Exists(requestPath)) throw new FileNotFoundException($"Source Graph export requests were not found: {requestPath}");
        var manifest = JsonUtility.FromJson<RequestManifest>(File.ReadAllText(requestPath));
        if (manifest == null || manifest.schema_version != RequestSchemaVersion || manifest.requests == null || manifest.requests.Length == 0) throw new InvalidOperationException("Unsupported or empty source Graph export request manifest.");
        var completed = 0;
        foreach (var request in manifest.requests)
        {
            try { ExportOne(request, manifest.source_dataset_id); completed++; }
            catch (Exception exception) { WriteReport(request, new ExportReport { created_at = DateTime.UtcNow.ToString("o"), candidate_id = request?.candidate_id, prefab_path = request?.prefab_path, graph_path = request?.graph_path, status = "error", reconstruction_status = "structure_only", missing_fields = Array.Empty<string>(), unsupported_components = Array.Empty<string>(), error = $"{exception.GetType().Name}: {exception.Message}" }); Debug.LogError($"Source PrefabGraph export failed for {request?.candidate_id}: {exception}"); }
        }
        Debug.Log($"Source PrefabGraph export completed: {completed}/{manifest.requests.Length}");
        if (completed != manifest.requests.Length) throw new InvalidOperationException($"Source PrefabGraph export failed for {manifest.requests.Length - completed} candidates.");
    }

    private static void ExportOne(SourceRequest request, string sourceDatasetId)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.candidate_id) || string.IsNullOrWhiteSpace(request.prefab_path) || string.IsNullOrWhiteSpace(request.graph_path) || string.IsNullOrWhiteSpace(request.report_path)) throw new InvalidOperationException("Source export request is incomplete.");
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(request.prefab_path);
        if (prefab == null) throw new FileNotFoundException($"Source Prefab could not be loaded: {request.prefab_path}");
        var nodes = new List<Node>(); var particles = new List<ParticleComponent>(); var renderers = new List<RendererComponent>(); var animations = new List<AnimationComponent>(); var materialPaths = new HashSet<string>(StringComparer.Ordinal); var meshPaths = new HashSet<string>(StringComparer.Ordinal); var missing = new HashSet<string>(StringComparer.Ordinal); var unsupported = new HashSet<string>(StringComparer.Ordinal); var nodeIds = new Dictionary<string, string>(StringComparer.Ordinal);
        var transforms = prefab.GetComponentsInChildren<Transform>(true);
        foreach (var transform in transforms.OrderBy(value => GetDepth(value)).ThenBy(value => BuildHierarchyPath(value)))
        {
            var path = BuildHierarchyPath(transform); var nodeId = $"n{nodes.Count:0000}"; nodeIds[path] = nodeId; var components = transform.GetComponents<Component>(); var types = components.Where(value => value != null).Select(value => value.GetType().FullName).Distinct().OrderBy(value => value).ToArray(); if (components.Any(value => value == null)) missing.Add("nodes[].missing_script");
            var componentSet = new HashSet<string>(types); foreach (var type in componentSet) if (!IsSupportedComponent(type)) unsupported.Add(type);
            if (transform is RectTransform) missing.Add("nodes[].rect_transform");
            nodes.Add(new Node { node_id = nodeId, name = transform.name, role = InferRole(transform.name, GetDepth(transform)), sibling_index = transform.GetSiblingIndex(), depth = GetDepth(transform), parent_node_id = null, hierarchy_path = path, active_self = transform.gameObject.activeSelf, component_types = types, transform = ToTransformData(transform) });
        }
        foreach (var node in nodes) node.parent_node_id = FindParentId(node, nodes);
        foreach (var transform in transforms)
        {
            var path = BuildHierarchyPath(transform); var nodeId = nodeIds[path]; var particle = transform.GetComponent<ParticleSystem>(); var particleRenderer = transform.GetComponent<ParticleSystemRenderer>(); if (particle != null) { if (particleRenderer == null) unsupported.Add("ParticleSystemWithoutParticleSystemRenderer"); var component = ReadParticle(particle, particleRenderer, nodeId, particles.Count, materialPaths, meshPaths, missing); particles.Add(component); if (component.parameters.serialized_modules.rotation_over_lifetime) unsupported.Add("ParticleSystem.rotation_over_lifetime"); if (component.parameters.serialized_modules.texture_sheet_animation) unsupported.Add("ParticleSystem.texture_sheet_animation"); if (component.parameters.serialized_modules.velocity_over_lifetime) unsupported.Add("ParticleSystem.velocity_over_lifetime"); }
            if (particle != null && particle.customData.enabled) unsupported.Add("ParticleSystem.custom_data");
            var renderer = transform.GetComponent<Renderer>(); if (renderer != null) { var component = ReadRenderer(renderer, nodeId, renderers.Count, materialPaths, meshPaths); renderers.Add(component); }
            var animator = transform.GetComponent<Animator>(); if (animator != null) animations.Add(new AnimationComponent { component_id = $"a{animations.Count:0000}", node_id = nodeId, animation_type = "UnityEngine.Animator", parameters = new AnimationParameters { clip_count = 0, duration_seconds = 0f } });
            var legacy = transform.GetComponent<Animation>(); if (legacy != null) animations.Add(new AnimationComponent { component_id = $"a{animations.Count:0000}", node_id = nodeId, animation_type = "UnityEngine.Animation", parameters = new AnimationParameters { clip_count = legacy.GetClipCount(), duration_seconds = 0f } });
            var director = transform.GetComponent<UnityEngine.Playables.PlayableDirector>(); if (director != null) animations.Add(new AnimationComponent { component_id = $"a{animations.Count:0000}", node_id = nodeId, animation_type = "UnityEngine.Playables.PlayableDirector", parameters = new AnimationParameters { clip_count = director.playableAsset == null ? 0 : 1, duration_seconds = director.playableAsset == null ? 0f : (float)director.playableAsset.duration } });
        }
        var reconstructable = missing.Count == 0 && unsupported.Count == 0 && nodes.All(node => node.component_types.All(type => type == "UnityEngine.Transform" || type == "UnityEngine.ParticleSystem" || type == "UnityEngine.ParticleSystemRenderer")) && particles.Count > 0;
        var graph = new Graph { schema_version = GraphSchemaVersion, graph_id = GraphId(request.prefab_path), source = new Source { source_kind = "unity_audit", prefab_path = request.prefab_path, source_example_id = request.candidate_id }, root_node_id = nodes[0].node_id, nodes = nodes.ToArray(), components = new Components { particle_systems = particles.ToArray(), renderers = renderers.ToArray(), animations = animations.ToArray() }, asset_bindings = new AssetBindings { materials = materialPaths.OrderBy(value => value).ToArray(), meshes = meshPaths.OrderBy(value => value).ToArray() }, reconstruction = new Reconstruction { status = reconstructable ? "reconstructable" : "structure_only", compiler_profile = reconstructable ? "particle_v1" : "none", missing_fields = missing.OrderBy(value => value).ToArray(), unsupported_components = unsupported.OrderBy(value => value).ToArray() }, training = new Training { eligible_tasks = reconstructable ? new[] { "component_prediction", "full_reconstruction", "hierarchy_modeling", "particle_parameter_modeling" } : new[] { "component_prediction", "hierarchy_modeling", "particle_parameter_modeling" }, excluded_tasks = reconstructable ? new[] { "aesthetic_preference", "prompt_condition" } : new[] { "aesthetic_preference", "prompt_condition", "full_reconstruction" }, aesthetic_label_source = "none" }, provenance = new Provenance { source_dataset_id = sourceDatasetId ?? "unity_source_export", source_run_id = null, exporter = "prefab_graph_source_unity.v1", assumptions = new[] { "All values were read through Unity AssetDatabase and component APIs.", "Source labels and directories are not aesthetic supervision.", "Unsupported or missing runtime context is retained as an explicit reconstruction limitation." } } };
        WriteJson(request.graph_path, graph); WriteReport(request, new ExportReport { created_at = DateTime.UtcNow.ToString("o"), candidate_id = request.candidate_id, prefab_path = request.prefab_path, graph_path = request.graph_path, status = "pass", reconstruction_status = graph.reconstruction.status, node_count = nodes.Count, particle_system_count = particles.Count, renderer_count = renderers.Count, animation_count = animations.Count, material_paths = graph.asset_bindings.materials, mesh_paths = graph.asset_bindings.meshes, missing_fields = graph.reconstruction.missing_fields, unsupported_components = graph.reconstruction.unsupported_components, error = null });
    }

    private static ParticleComponent ReadParticle(ParticleSystem system, ParticleSystemRenderer renderer, string nodeId, int index, HashSet<string> materials, HashSet<string> meshes, HashSet<string> missing)
    {
        var main = system.main; var emission = system.emission; var shape = system.shape;
        var color = system.colorOverLifetime; var size = system.sizeOverLifetime;
        var startColor = main.startColor.color;
        var endColor = color.enabled ? color.color.Evaluate(1f) : startColor;
        var bursts = new ParticleSystem.Burst[emission.burstCount];
        emission.GetBursts(bursts);
        var burstCount = bursts.Sum(value => (int)value.maxCount);
        var meshPaths = renderer == null ? Array.Empty<string>() : AssetPaths(new UnityEngine.Object[] { renderer.mesh }, meshes);
        var materialPaths = renderer == null ? Array.Empty<string>() : AssetPaths(renderer.sharedMaterials, materials);
        var parameters = new ParticleParameters
        {
            duration_seconds = main.duration, start_delay_max = main.startDelay.constantMax,
            looping = main.loop, simulation_space = main.simulationSpace.ToString(), max_particles = main.maxParticles,
            start_lifetime_max = main.startLifetime.constantMax, start_speed_max = main.startSpeed.constantMax,
            start_size_max = main.startSize.constantMax, start_size_3d = main.startSize3D,
            start_size_x_max = main.startSizeX.constantMax, start_size_y_max = main.startSizeY.constantMax, start_size_z_max = main.startSizeZ.constantMax,
            start_rotation_max = main.startRotation.constantMax, gravity_modifier_max = main.gravityModifier.constantMax,
            start_color_rgba = ToArray(startColor), end_color_rgba = ToArray(endColor),
            material_color_mode = "preserve_template",
            emission_enabled = emission.enabled, emission_rate_over_time_max = emission.rateOverTime.constantMax,
            burst_particle_count = burstCount, shape_enabled = shape.enabled,
            shape_type = shape.enabled ? shape.shapeType.ToString() : "disabled", shape_radius = shape.radius,
            color_over_lifetime_enabled = color.enabled, size_over_lifetime_enabled = size.enabled,
            end_size_multiplier = size.enabled ? size.size.curve.Evaluate(1f) : 1f,
            renderer_mode = renderer == null ? "missing" : renderer.renderMode.ToString(), sorting_order = renderer == null ? 0 : renderer.sortingOrder,
            serialized_modules = new ModuleSnapshot { emission = emission.enabled, shape = shape.enabled, color_over_lifetime = color.enabled, size_over_lifetime = size.enabled, rotation_over_lifetime = system.rotationOverLifetime.enabled, texture_sheet_animation = system.textureSheetAnimation.enabled, velocity_over_lifetime = system.velocityOverLifetime.enabled }
        };
        if (main.startColor.mode != ParticleSystemGradientMode.Color)
            missing.Add($"particle[{nodeId}].start_color_distribution:{main.startColor.mode}");
        if (color.enabled)
        {
            try
            {
                parameters.color_over_lifetime_gradient = EffectDemoParticleColorGradient.FromUnity(color.color);
                parameters.color_over_lifetime_gradient.ToUnity();
            }
            catch (Exception exception) when (exception is NotSupportedException || exception is InvalidOperationException)
            {
                parameters.color_over_lifetime_gradient = null;
                missing.Add($"particle[{nodeId}].color_over_lifetime_gradient:{exception.Message}");
            }
        }
        parameters.serialized_modules.custom_data = system.customData.enabled;
        return new ParticleComponent { component_id = $"p{index:0000}", node_id = nodeId, parameters = parameters, material_paths = materialPaths, mesh_paths = meshPaths };
    }

    private static RendererComponent ReadRenderer(Renderer renderer, string nodeId, int index, HashSet<string> materials, HashSet<string> meshes)
    {
        var particle = renderer as ParticleSystemRenderer; var meshFilter = renderer.GetComponent<MeshFilter>(); var skinned = renderer as SkinnedMeshRenderer; var mesh = particle != null ? particle.mesh : skinned != null ? skinned.sharedMesh : meshFilter == null ? null : meshFilter.sharedMesh; var mode = particle == null ? null : particle.renderMode.ToString(); var sorting = renderer is ParticleSystemRenderer particleRenderer ? particleRenderer.sortingOrder : renderer.sortingOrder; var streams = new List<ParticleSystemVertexStream>(); if (particle != null) particle.GetActiveVertexStreams(streams); return new RendererComponent { component_id = $"r{index:0000}", node_id = nodeId, renderer_type = renderer.GetType().Name, enabled = renderer.enabled, parameters = new RendererParameters { particle_render_mode = mode, sorting_order = sorting, active_vertex_streams = streams.Select(value => value.ToString()).ToArray() }, material_paths = AssetPaths(renderer.sharedMaterials, materials), mesh_paths = AssetPaths(new UnityEngine.Object[] { mesh }, meshes) };
    }

    private static string[] AssetPaths(UnityEngine.Object[] assets, HashSet<string> collector) { var paths = new List<string>(); foreach (var asset in assets ?? Array.Empty<UnityEngine.Object>()) { if (asset == null) continue; var path = AssetDatabase.GetAssetPath(asset); if (string.IsNullOrWhiteSpace(path)) continue; collector.Add(path); paths.Add(path); } return paths.Distinct().OrderBy(value => value).ToArray(); }
    private static string FindParentId(Node node, List<Node> nodes) { if (node.depth == 0) return null; var parentPath = node.hierarchy_path.Substring(0, node.hierarchy_path.LastIndexOf('/')); return nodes.First(value => value.hierarchy_path == parentPath).node_id; }
    private static bool IsSupportedComponent(string type) { return type == "UnityEngine.Transform" || type == "UnityEngine.ParticleSystem" || type == "UnityEngine.ParticleSystemRenderer"; }
    private static string InferRole(string name, int depth) { var lower = name.ToLowerInvariant(); if (depth == 0) return "root"; if (lower.Contains("core") || lower.Contains("main") || lower.Contains("zhuti")) return "core"; if (lower.Contains("hit") || lower.Contains("impact") || lower.Contains("spark")) return "hit"; if (lower.Contains("residual") || lower.Contains("after") || lower.Contains("tail")) return "residual"; if (lower.Contains("support") || lower.Contains("glow") || lower.Contains("guang")) return "support"; return "unclassified"; }
    private static string BuildHierarchyPath(Transform transform) { var parts = new List<string>(); for (var current = transform; current != null; current = current.parent) parts.Add($"{current.name}[{current.GetSiblingIndex()}]"); parts.Reverse(); return string.Join("/", parts); }
    private static int GetDepth(Transform transform) { var depth = 0; for (var current = transform.parent; current != null; current = current.parent) depth++; return depth; }
    private static TransformData ToTransformData(Transform value) { return new TransformData { local_position = new[] { value.localPosition.x, value.localPosition.y, value.localPosition.z }, local_rotation = new[] { value.localRotation.x, value.localRotation.y, value.localRotation.z, value.localRotation.w }, local_scale = new[] { value.localScale.x, value.localScale.y, value.localScale.z } }; }
    private static float[] ToArray(Color value) { return new[] { value.r, value.g, value.b, value.a }; }
    private static string GraphId(string path) { using (var sha = SHA256.Create()) return "pfg_" + string.Concat(sha.ComputeHash(Encoding.UTF8.GetBytes(path)).Take(10).Select(value => value.ToString("x2"))); }
    private static string CommandLineValue(string key) { var args = Environment.GetCommandLineArgs(); for (var index = 0; index < args.Length - 1; index++) if (string.Equals(args[index], key, StringComparison.OrdinalIgnoreCase)) return args[index + 1]; return null; }
    private static void WriteJson(string path, object value) { var parent = Path.GetDirectoryName(path); if (!string.IsNullOrWhiteSpace(parent)) Directory.CreateDirectory(parent); File.WriteAllText(path, JsonUtility.ToJson(value, true) + "\n"); }
    private static void WriteReport(SourceRequest request, ExportReport report) { if (request != null && !string.IsNullOrWhiteSpace(request.report_path)) WriteJson(request.report_path, report); }
}
