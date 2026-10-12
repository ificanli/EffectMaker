using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class EffectDemoPrefabGraphReadback
{
    private const string GraphSchemaVersion = "vfx_prefab_graph.v1";
    private const string ResultSchemaVersion = "vfx_prefab_graph_readback_result.v1";

    [Serializable]
    private sealed class Graph
    {
        public string schema_version;
        public string graph_id;
        public Source source;
        public Condition condition;
        public string root_node_id;
        public Node[] nodes;
        public Components components;
        public AssetBindings asset_bindings;
        public Reconstruction reconstruction;
        public Training training;
        public Provenance provenance;
    }

    [Serializable]
    private sealed class Source { public string source_kind; public string prefab_path; public string source_example_id; }
    [Serializable]
    private sealed class Condition { public string prompt; public string effect_family; public string style_family; public int seed; public string parent_prefab_path; }
    [Serializable]
    private sealed class Node
    {
        public string node_id;
        public string name;
        public string role;
        public int sibling_index;
        public int depth;
        public string parent_node_id;
        public string hierarchy_path;
        public bool active_self;
        public string[] component_types;
        public TransformData transform;
    }

    [Serializable]
    private sealed class TransformData { public float[] local_position; public float[] local_rotation; public float[] local_scale; }
    [Serializable]
    private sealed class Components { public ParticleComponent[] particle_systems; public RendererComponent[] renderers; public AnimationComponent[] animations; }
    [Serializable]
    private sealed class ParticleComponent
    {
        public string component_id;
        public string node_id;
        public ParticleParameters parameters;
        public string[] material_paths;
        public string[] mesh_paths;
    }

    [Serializable]
    private sealed class ParticleParameters
    {
        public float duration_seconds;
        public float start_delay_max;
        public bool looping;
        public string simulation_space;
        public int max_particles;
        public float start_lifetime_max;
        public float start_speed_max;
        public float start_size_max;
        public bool start_size_3d;
        public float start_size_x_max;
        public float start_size_y_max;
        public float start_size_z_max;
        public float start_rotation_max;
        public float gravity_modifier_max;
        public float[] start_color_rgba;
        public float[] end_color_rgba;
        public EffectDemoParticleColorGradient color_over_lifetime_gradient;
        public string material_color_mode;
        public bool emission_enabled;
        public float emission_rate_over_time_max;
        public int burst_particle_count;
        public bool shape_enabled;
        public string shape_type;
        public float shape_radius;
        public bool color_over_lifetime_enabled;
        public bool size_over_lifetime_enabled;
        public float end_size_multiplier;
        public string renderer_mode;
        public int sorting_order;
        public string texture_profile;
        public string shader_profile;
        public string material_template_path;
        public string serialized_modules;
    }

    [Serializable]
    private sealed class RendererComponent
    {
        public string component_id;
        public string node_id;
        public string renderer_type;
        public bool enabled;
        public RendererParameters parameters;
        public string[] material_paths;
        public string[] mesh_paths;
    }

    [Serializable]
    private sealed class RendererParameters { public string particle_render_mode; public int sorting_order; public string[] active_vertex_streams; }
    [Serializable]
    private sealed class AnimationComponent { public string component_id; public string node_id; public string animation_type; public Dictionary<string, string> parameters; }
    [Serializable]
    private sealed class AssetBindings { public string[] materials; public string[] meshes; }
    [Serializable]
    private sealed class Reconstruction { public string status; public string compiler_profile; public string[] missing_fields; public string[] unsupported_components; }
    [Serializable]
    private sealed class Training { public string[] eligible_tasks; public string[] excluded_tasks; public string aesthetic_label_source; }
    [Serializable]
    private sealed class Provenance { public string source_dataset_id; public string source_run_id; public string exporter; public string[] assumptions; }

    // JsonUtility writes null strings as empty strings. The readback Graph omits
    // the optional condition object so a no-parent result remains schema-valid.
    [Serializable]
    private sealed class ReadbackGraph
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

    [Serializable]
    private sealed class ReadbackResult
    {
        public string schema_version = ResultSchemaVersion;
        public string created_at;
        public string graph_id;
        public string input_graph_path;
        public string prefab_path;
        public string output_graph_path;
        public string status;
        public bool unity_api_readback;
        public bool source_prefab_instantiated;
        public int node_count;
        public int particle_system_count;
        public int renderer_count;
        public string[] material_paths;
        public string[] mesh_paths;
        public string[] differences;
        public string[] allowed_normalizations;
        public string error;
    }

    public static void ReadbackFromCommandLine()
    {
        var inputGraphPath = CommandLineValue("-prefabGraphPath");
        var prefabPath = CommandLineValue("-prefabGraphInput");
        var outputGraphPath = CommandLineValue("-prefabGraphReadbackOutput");
        var resultPath = CommandLineValue("-prefabGraphReadbackResult");
        ReadbackResult result = null;
        try
        {
            var input = ReadGraph(inputGraphPath);
            result = Readback(input, inputGraphPath, prefabPath, outputGraphPath);
            WriteJson(resultPath, result);
            if (result.status != "pass")
                throw new InvalidOperationException(result.error ?? "PrefabGraph readback failed.");
            Debug.Log($"PrefabGraph Unity API readback completed: {result.graph_id} -> {result.output_graph_path}");
        }
        catch (Exception exception)
        {
            result = result ?? new ReadbackResult
            {
                created_at = DateTime.UtcNow.ToString("o"),
                input_graph_path = inputGraphPath,
                prefab_path = prefabPath,
                output_graph_path = outputGraphPath,
                status = "error",
                unity_api_readback = false,
                source_prefab_instantiated = false,
                differences = Array.Empty<string>(),
                allowed_normalizations = Array.Empty<string>(),
                material_paths = Array.Empty<string>(),
                mesh_paths = Array.Empty<string>(),
            };
            result.error = $"{exception.GetType().Name}: {exception.Message}";
            WriteJson(resultPath, result);
            Debug.LogError($"PrefabGraph Unity API readback failed: {exception}");
            throw;
        }
    }

    private static Graph ReadGraph(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            throw new FileNotFoundException($"Input PrefabGraph was not found: {path}");
        var graph = JsonUtility.FromJson<Graph>(File.ReadAllText(path));
        if (graph == null || graph.schema_version != GraphSchemaVersion || string.IsNullOrWhiteSpace(graph.graph_id))
            throw new InvalidOperationException("Unsupported or incomplete PrefabGraph input.");
        if (graph.nodes == null || graph.nodes.Length == 0 || graph.components == null)
            throw new InvalidOperationException("PrefabGraph input has no nodes or components.");
        return graph;
    }

    private static ReadbackResult Readback(Graph input, string inputPath, string prefabPath, string outputGraphPath)
    {
        if (string.IsNullOrWhiteSpace(prefabPath) || !prefabPath.StartsWith("Assets/", StringComparison.Ordinal) || !prefabPath.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("PrefabGraph readback requires a project-relative Assets/*.prefab input.");
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
        if (prefab == null)
            throw new FileNotFoundException($"Prefab could not be loaded through AssetDatabase: {prefabPath}");

        var nodeByPath = input.nodes.ToDictionary(node => node.hierarchy_path, StringComparer.Ordinal);
        var particleByNode = input.components.particle_systems?.ToDictionary(value => value.node_id, StringComparer.Ordinal)
            ?? new Dictionary<string, ParticleComponent>(StringComparer.Ordinal);
        var rendererByNode = input.components.renderers?.ToDictionary(value => value.node_id, StringComparer.Ordinal)
            ?? new Dictionary<string, RendererComponent>(StringComparer.Ordinal);
        var outputNodes = new List<Node>();
        var outputParticles = new List<ParticleComponent>();
        var outputRenderers = new List<RendererComponent>();
        var materials = new HashSet<string>(StringComparer.Ordinal);
        var meshes = new HashSet<string>(StringComparer.Ordinal);
        var differences = new List<string>();
        var allowed = new List<string>();

        ReadTransformTree(prefab.transform, null, nodeByPath, particleByNode, rendererByNode, outputNodes, outputParticles, outputRenderers, materials, meshes, differences, allowed);
        outputNodes.Sort((left, right) => string.CompareOrdinal(left.node_id, right.node_id));
        outputParticles.Sort((left, right) => string.CompareOrdinal(left.component_id, right.component_id));
        outputRenderers.Sort((left, right) => string.CompareOrdinal(left.component_id, right.component_id));

        var output = new ReadbackGraph
        {
            schema_version = GraphSchemaVersion,
            graph_id = input.graph_id,
            source = new Source { source_kind = "generated", prefab_path = prefabPath, source_example_id = input.source?.source_example_id },
            root_node_id = input.root_node_id,
            nodes = outputNodes.ToArray(),
            components = new Components { particle_systems = outputParticles.ToArray(), renderers = outputRenderers.ToArray(), animations = input.components.animations ?? Array.Empty<AnimationComponent>() },
            asset_bindings = new AssetBindings { materials = materials.OrderBy(value => value).ToArray(), meshes = meshes.OrderBy(value => value).ToArray() },
            reconstruction = new Reconstruction { status = "reconstructable", compiler_profile = "particle_v1", missing_fields = Array.Empty<string>(), unsupported_components = Array.Empty<string>() },
            training = input.training ?? new Training { eligible_tasks = Array.Empty<string>(), excluded_tasks = new[] { "aesthetic_preference", "prompt_condition" }, aesthetic_label_source = "ai_hypothesis" },
            provenance = new Provenance
            {
                source_dataset_id = input.provenance?.source_dataset_id ?? "readback",
                source_run_id = input.provenance?.source_run_id,
                exporter = "prefab_graph_readback.v1",
                assumptions = new[] { "Graph exported through Unity AssetDatabase and component APIs.", "Material and mesh paths point to the compiled Prefab output assets." },
            },
        };
        WriteJson(outputGraphPath, output);
        return new ReadbackResult
        {
            created_at = DateTime.UtcNow.ToString("o"),
            graph_id = input.graph_id,
            input_graph_path = inputPath,
            prefab_path = prefabPath,
            output_graph_path = outputGraphPath,
            status = differences.Count == 0 ? "pass" : "mismatch",
            unity_api_readback = true,
            source_prefab_instantiated = false,
            node_count = outputNodes.Count,
            particle_system_count = outputParticles.Count,
            renderer_count = outputRenderers.Count,
            material_paths = materials.OrderBy(value => value).ToArray(),
            mesh_paths = meshes.OrderBy(value => value).ToArray(),
            differences = differences.ToArray(),
            allowed_normalizations = allowed.ToArray(),
            error = differences.Count == 0 ? null : "Unity API readback differs from input Graph.",
        };
    }

    private static void ReadTransformTree(
        Transform transform,
        string parentNodeId,
        Dictionary<string, Node> nodeByPath,
        Dictionary<string, ParticleComponent> particleByNode,
        Dictionary<string, RendererComponent> rendererByNode,
        List<Node> nodes,
        List<ParticleComponent> particles,
        List<RendererComponent> renderers,
        HashSet<string> materials,
        HashSet<string> meshes,
        List<string> differences,
        List<string> allowed)
    {
        var path = BuildHierarchyPath(transform);
        if (!nodeByPath.TryGetValue(path, out var inputNode))
        {
            differences.Add($"nodes[{path}] unexpected hierarchy path");
            return;
        }
        var node = new Node
        {
            node_id = inputNode.node_id,
            name = transform.name,
            role = inputNode.role,
            sibling_index = transform.GetSiblingIndex(),
            depth = GetDepth(transform),
            parent_node_id = parentNodeId,
            hierarchy_path = path,
            active_self = transform.gameObject.activeSelf,
            component_types = transform.GetComponents<Component>().Where(value => value != null).Select(value => value.GetType().FullName).Distinct().OrderBy(value => value).ToArray(),
            transform = ToTransformData(transform),
        };
        nodes.Add(node);
        if (string.IsNullOrWhiteSpace(parentNodeId))
            allowed.Add($"node[{node.node_id}].parent_node_id: Unity JsonUtility serializes the root null parent as an empty string");
        CompareNode(inputNode, node, differences);

        var particle = transform.GetComponent<ParticleSystem>();
        if (particle != null)
        {
            if (!particleByNode.TryGetValue(inputNode.node_id, out var inputParticle))
                differences.Add($"particle[{path}] missing from input Graph");
            else
            {
                var outputParticle = ReadParticle(inputParticle, particle, inputNode.node_id, rendererByNode, materials, meshes, differences, allowed);
                particles.Add(outputParticle);
            }
        }
        var particleRenderer = transform.GetComponent<ParticleSystemRenderer>();
        if (particleRenderer != null)
        {
            if (!rendererByNode.TryGetValue(inputNode.node_id, out var inputRenderer))
                differences.Add($"renderer[{path}] missing from input Graph");
            else
                renderers.Add(ReadRenderer(inputRenderer, particleRenderer, inputNode.node_id, materials, meshes, differences));
        }
        for (var index = 0; index < transform.childCount; index++)
            ReadTransformTree(transform.GetChild(index), inputNode.node_id, nodeByPath, particleByNode, rendererByNode, nodes, particles, renderers, materials, meshes, differences, allowed);
    }

    private static ParticleComponent ReadParticle(ParticleComponent input, ParticleSystem system, string nodeId, Dictionary<string, RendererComponent> rendererByNode, HashSet<string> materials, HashSet<string> meshes, List<string> differences, List<string> allowed)
    {
        var main = system.main;
        var emission = system.emission;
        var shape = system.shape;
        var colorLifetime = system.colorOverLifetime;
        var sizeLifetime = system.sizeOverLifetime;
        if (main.startColor.mode != ParticleSystemGradientMode.Color)
            differences.Add($"particle[{nodeId}].start_color_mode is {main.startColor.mode}; deterministic Color required");
        var startColor = main.startColor.color;
        var endColor = colorLifetime.enabled ? colorLifetime.color.gradient.Evaluate(1f) : startColor;
        var bursts = new ParticleSystem.Burst[emission.burstCount];
        emission.GetBursts(bursts);
        var burstCount = bursts.Sum(value => (int)value.maxCount);
        var endSize = sizeLifetime.enabled ? sizeLifetime.size.curve.Evaluate(1f) : 1f;
        var output = new ParticleComponent
        {
            component_id = input.component_id,
            node_id = nodeId,
            parameters = new ParticleParameters
            {
                duration_seconds = main.duration,
                start_delay_max = main.startDelay.constantMax,
                looping = main.loop,
                simulation_space = main.simulationSpace.ToString(),
                max_particles = main.maxParticles,
                start_lifetime_max = main.startLifetime.constantMax,
                start_speed_max = main.startSpeed.constantMax,
                start_size_max = main.startSize.constantMax,
                start_size_3d = main.startSize3D,
                start_size_x_max = main.startSizeX.constantMax,
                start_size_y_max = main.startSizeY.constantMax,
                start_size_z_max = main.startSizeZ.constantMax,
                start_rotation_max = main.startRotation.constantMax,
                gravity_modifier_max = main.gravityModifier.constantMax,
                start_color_rgba = ToArray(startColor),
                end_color_rgba = ToArray(endColor),
                color_over_lifetime_gradient = EffectDemoParticleColorGradient.HasData(input.parameters?.color_over_lifetime_gradient) && colorLifetime.enabled
                    ? EffectDemoParticleColorGradient.FromUnity(colorLifetime.color) : null,
                material_color_mode = input.parameters?.material_color_mode,
                emission_enabled = emission.enabled,
                emission_rate_over_time_max = emission.rateOverTime.constantMax,
                burst_particle_count = burstCount,
                shape_enabled = shape.enabled,
                shape_type = shape.enabled ? shape.shapeType.ToString() : "disabled",
                shape_radius = shape.enabled ? shape.radius : 0f,
                color_over_lifetime_enabled = colorLifetime.enabled,
                size_over_lifetime_enabled = sizeLifetime.enabled,
                end_size_multiplier = endSize,
                renderer_mode = rendererByNode.TryGetValue(nodeId, out var renderer) ? renderer.parameters?.particle_render_mode : "Billboard",
                sorting_order = rendererByNode.TryGetValue(nodeId, out renderer) ? renderer.parameters?.sorting_order ?? 0 : 0,
                texture_profile = input.parameters?.texture_profile,
                shader_profile = input.parameters?.shader_profile,
                material_template_path = input.parameters?.material_template_path,
                serialized_modules = "unity_api_readback",
            },
            material_paths = Array.Empty<string>(),
            mesh_paths = Array.Empty<string>(),
        };
        CompareParticle(input, output, differences);
        if (EffectDemoParticleColorGradient.HasData(input.parameters?.color_over_lifetime_gradient)
            && !EffectDemoParticleColorGradient.Equivalent(input.parameters.color_over_lifetime_gradient, output.parameters.color_over_lifetime_gradient))
            differences.Add($"particle[{nodeId}].color_over_lifetime_gradient differs");
        var particleRenderer = system.GetComponent<ParticleSystemRenderer>();
        if (particleRenderer != null)
        {
            ComparePreservedMaterialColors(input, particleRenderer, differences);
            output.material_paths = AssetPaths(particleRenderer.sharedMaterials, materials);
            output.mesh_paths = AssetPaths(new[] { particleRenderer.mesh }, meshes);
            if (input.material_paths == null || input.material_paths.Length == 0)
                allowed.Add($"particle[{nodeId}].material_paths: generated output material replaces template binding");
            if (input.mesh_paths != null && input.mesh_paths.Length > 0 && !new HashSet<string>(input.mesh_paths).SetEquals(output.mesh_paths))
                differences.Add($"particle[{nodeId}].mesh_paths differ");
        }
        return output;
    }

    private static void ComparePreservedMaterialColors(ParticleComponent input, ParticleSystemRenderer renderer, List<string> differences)
    {
        if (input.parameters?.material_color_mode != "preserve_template") return;
        var templatePath = input.parameters.material_template_path;
        if (string.IsNullOrWhiteSpace(templatePath))
            templatePath = input.material_paths?.FirstOrDefault();
        if (string.IsNullOrWhiteSpace(templatePath))
        {
            differences.Add($"particle[{input.node_id}].preserved material colors have no explicit template to verify");
            return;
        }
        var template = AssetDatabase.LoadAssetAtPath<Material>(templatePath);
        var actual = renderer.sharedMaterial;
        if (template == null || actual == null || template.shader != actual.shader)
        {
            differences.Add($"particle[{input.node_id}].preserved material Shader/template differs");
            return;
        }
        for (var index = 0; index < template.shader.GetPropertyCount(); index++)
        {
            if (template.shader.GetPropertyType(index) != UnityEngine.Rendering.ShaderPropertyType.Color) continue;
            var property = template.shader.GetPropertyName(index);
            if (!Close(ToArray(template.GetColor(property)), ToArray(actual.GetColor(property))))
                differences.Add($"particle[{input.node_id}].preserved material color {property} differs");
        }
    }

    private static RendererComponent ReadRenderer(RendererComponent input, ParticleSystemRenderer renderer, string nodeId, HashSet<string> materials, HashSet<string> meshes, List<string> differences)
    {
        var output = new RendererComponent
        {
            component_id = input.component_id,
            node_id = nodeId,
            renderer_type = renderer.GetType().Name,
            enabled = renderer.enabled,
            parameters = new RendererParameters { particle_render_mode = renderer.renderMode.ToString(), sorting_order = renderer.sortingOrder, active_vertex_streams = ActiveVertexStreams(renderer) },
            material_paths = AssetPaths(renderer.sharedMaterials, materials),
            mesh_paths = AssetPaths(new[] { renderer.mesh }, meshes),
        };
        if (input.renderer_type != output.renderer_type) differences.Add($"renderer[{nodeId}].renderer_type: {input.renderer_type} != {output.renderer_type}");
        if (input.enabled != output.enabled) differences.Add($"renderer[{nodeId}].enabled differs");
        if (input.parameters != null && input.parameters.particle_render_mode != output.parameters.particle_render_mode) differences.Add($"renderer[{nodeId}].particle_render_mode differs");
        if (input.parameters != null && input.parameters.sorting_order != output.parameters.sorting_order) differences.Add($"renderer[{nodeId}].sorting_order differs");
        if (input.parameters?.active_vertex_streams != null && input.parameters.active_vertex_streams.Length > 0 && !input.parameters.active_vertex_streams.SequenceEqual(output.parameters.active_vertex_streams ?? Array.Empty<string>(), StringComparer.Ordinal)) differences.Add($"renderer[{nodeId}].active_vertex_streams differ (order is significant)");
        if (input.mesh_paths != null && input.mesh_paths.Length > 0 && !new HashSet<string>(input.mesh_paths).SetEquals(output.mesh_paths))
            differences.Add($"renderer[{nodeId}].mesh_paths differ");
        return output;
    }

    private static string[] ActiveVertexStreams(ParticleSystemRenderer renderer)
    {
        var streams = new List<ParticleSystemVertexStream>();
        renderer.GetActiveVertexStreams(streams);
        return streams.Select(value => value.ToString()).ToArray();
    }

    private static string[] AssetPaths(UnityEngine.Object[] assets, HashSet<string> collector)
    {
        var paths = new List<string>();
        foreach (var asset in assets ?? Array.Empty<UnityEngine.Object>())
        {
            if (asset == null) continue;
            var path = AssetDatabase.GetAssetPath(asset);
            if (string.IsNullOrWhiteSpace(path)) continue;
            collector.Add(path);
            paths.Add(path);
        }
        return paths.Distinct().OrderBy(value => value).ToArray();
    }

    private static string BuildHierarchyPath(Transform transform)
    {
        var parts = new List<string>();
        var current = transform;
        while (current != null)
        {
            parts.Add($"{current.name}[{current.GetSiblingIndex()}]");
            current = current.parent;
        }
        parts.Reverse();
        return string.Join("/", parts);
    }

    private static int GetDepth(Transform transform)
    {
        var depth = 0;
        for (var current = transform.parent; current != null; current = current.parent) depth++;
        return depth;
    }

    private static TransformData ToTransformData(Transform value) => new TransformData
    {
        local_position = new[] { value.localPosition.x, value.localPosition.y, value.localPosition.z },
        local_rotation = new[] { value.localRotation.x, value.localRotation.y, value.localRotation.z, value.localRotation.w },
        local_scale = new[] { value.localScale.x, value.localScale.y, value.localScale.z },
    };

    private static float[] ToArray(Color value) => new[] { value.r, value.g, value.b, value.a };
    private static bool Close(float left, float right) => Mathf.Abs(left - right) <= 0.0001f;
    private static bool Close(float[] left, float[] right) => left != null && right != null && left.Length == right.Length && left.Zip(right, Close).All(value => value);

    private static void CompareNode(Node input, Node output, List<string> differences)
    {
        if (input.name != output.name || input.sibling_index != output.sibling_index || input.depth != output.depth || NormalizeEmpty(input.parent_node_id) != NormalizeEmpty(output.parent_node_id) || input.active_self != output.active_self)
            differences.Add($"node[{input.node_id}] hierarchy metadata differs");
        if (!Close(input.transform?.local_position, output.transform.local_position) || !Close(input.transform?.local_rotation, output.transform.local_rotation) || !Close(input.transform?.local_scale, output.transform.local_scale))
            differences.Add($"node[{input.node_id}].transform differs");
        var expected = new HashSet<string>(input.component_types ?? Array.Empty<string>());
        var actual = new HashSet<string>(output.component_types ?? Array.Empty<string>());
        expected.ExceptWith(actual);
        if (expected.Count > 0) differences.Add($"node[{input.node_id}] missing components: {string.Join(",", expected)}");
    }

    private static void CompareParticle(ParticleComponent input, ParticleComponent output, List<string> differences)
    {
        var left = input.parameters; var right = output.parameters;
        if (left == null || right == null) { differences.Add($"particle[{input.node_id}] parameters missing"); return; }
        if (!Close(left.duration_seconds, right.duration_seconds) || !Close(left.start_delay_max, right.start_delay_max) || left.looping != right.looping || left.simulation_space != right.simulation_space || left.max_particles != right.max_particles || !Close(left.start_lifetime_max, right.start_lifetime_max) || !Close(left.start_speed_max, right.start_speed_max) || (!left.start_size_3d && !Close(left.start_size_max, right.start_size_max)) || left.start_size_3d != right.start_size_3d || (left.start_size_3d && (!Close(left.start_size_x_max, right.start_size_x_max) || !Close(left.start_size_y_max, right.start_size_y_max) || !Close(left.start_size_z_max, right.start_size_z_max))) || !Close(left.start_rotation_max, right.start_rotation_max) || !Close(left.gravity_modifier_max, right.gravity_modifier_max) || !Close(left.start_color_rgba, right.start_color_rgba) || left.emission_enabled != right.emission_enabled || !Close(left.emission_rate_over_time_max, right.emission_rate_over_time_max) || left.burst_particle_count != right.burst_particle_count || left.shape_enabled != right.shape_enabled || left.shape_type != right.shape_type || (left.shape_enabled && !Close(left.shape_radius, right.shape_radius)) || left.color_over_lifetime_enabled != right.color_over_lifetime_enabled || left.size_over_lifetime_enabled != right.size_over_lifetime_enabled || !Close(left.end_size_multiplier, right.end_size_multiplier) || !Close(left.end_color_rgba, right.end_color_rgba))
            differences.Add($"particle[{input.node_id}].parameters differ");
    }

    private static string NormalizeEmpty(string value) => string.IsNullOrWhiteSpace(value) ? null : value;

    private static string CommandLineValue(string key)
    {
        var args = Environment.GetCommandLineArgs();
        for (var index = 0; index < args.Length - 1; index++) if (string.Equals(args[index], key, StringComparison.OrdinalIgnoreCase)) return args[index + 1];
        return null;
    }

    private static void WriteJson(string path, object value)
    {
        if (string.IsNullOrWhiteSpace(path)) return;
        var parent = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(parent)) Directory.CreateDirectory(parent);
        File.WriteAllText(path, JsonUtility.ToJson(value, true) + "\n");
    }
}
