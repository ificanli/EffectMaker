using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class EffectDemoPrefabGraphCompiler
{
    private const string SchemaVersion = "vfx_prefab_graph.v1";

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
        public Reconstruction reconstruction;
    }

    [Serializable]
    private sealed class Source
    {
        public string source_kind;
        public string prefab_path;
        public string source_example_id;
    }

    [Serializable]
    private sealed class Condition
    {
        public string prompt;
        public string effect_family;
        public string style_family;
        public int seed;
        public string parent_prefab_path;
    }

    [Serializable]
    private sealed class Node
    {
        public string node_id;
        public string name;
        public string role;
        public int sibling_index;
        public int depth;
        public string parent_node_id;
        public bool active_self;
        public string[] component_types;
        public TransformData transform;
    }

    [Serializable]
    private sealed class TransformData
    {
        public float[] local_position;
        public float[] local_rotation;
        public float[] local_scale;
    }

    [Serializable]
    private sealed class Components
    {
        public ParticleComponent[] particle_systems;
        public RendererComponent[] renderers;
    }

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
        public string texture_asset_path;
        public string texture_property_name;
        public string shader_profile;
        public string material_template_path;
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
    private sealed class RendererParameters
    {
        public string particle_render_mode;
        public int sorting_order;
        public string[] active_vertex_streams;
    }

    [Serializable]
    private sealed class Reconstruction
    {
        public string status;
        public string compiler_profile;
        public string[] missing_fields;
        public string[] unsupported_components;
    }

    [Serializable]
    private sealed class CompileResult
    {
        public string schema_version = "vfx_prefab_graph_compile_result.v1";
        public string created_at;
        public string graph_id;
        public string status;
        public string output_prefab_path;
        public bool source_prefab_read;
        public int node_count;
        public int particle_system_count;
        public string[] generated_material_paths;
        public string[] generated_texture_paths;
        public string[] bound_texture_paths;
        public string[] generated_shader_names;
        public string[] material_template_paths;
        public MaterialTextureReadback[] material_texture_readbacks;
        public bool planned_texture_readback_match;
        public string error;
    }

    [Serializable]
    private sealed class MaterialTextureReadback
    {
        public string renderer_name;
        public string material_path;
        public string shader_name;
        public string property_name;
        public string texture_path;
    }

    [Serializable]
    private sealed class BatchCompileRequest
    {
        public BatchCompileItem[] requests;
    }

    [Serializable]
    private sealed class BatchCompileItem
    {
        public string graph_path;
        public string output_prefab_path;
        public string result_path;
    }

    public static void CompileFromCommandLine()
    {
        var graphPath = CommandLineValue("-prefabGraphPath");
        var outputPrefabPath = CommandLineValue("-prefabGraphOutput");
        var resultPath = CommandLineValue("-prefabGraphResult");
        CompileResult result = null;
        try
        {
            result = Compile(graphPath, outputPrefabPath);
            WriteResult(resultPath, result);
            Debug.Log($"PrefabGraph compiled without a parent Prefab: {result.graph_id} -> {result.output_prefab_path}");
        }
        catch (Exception exception)
        {
            result = result ?? new CompileResult
            {
                created_at = DateTime.UtcNow.ToString("o"),
                status = "error",
                output_prefab_path = outputPrefabPath,
                source_prefab_read = false,
                generated_material_paths = Array.Empty<string>(),
                generated_texture_paths = Array.Empty<string>(),
                bound_texture_paths = Array.Empty<string>(),
                generated_shader_names = Array.Empty<string>(),
                material_template_paths = Array.Empty<string>(),
                material_texture_readbacks = Array.Empty<MaterialTextureReadback>(),
                planned_texture_readback_match = false,
            };
            result.error = $"{exception.GetType().Name}: {exception.Message}";
            WriteResult(resultPath, result);
            Debug.LogError($"PrefabGraph compile failed: {exception}");
            throw;
        }
    }

    public static void CompileBatchFromCommandLine()
    {
        var requestPath = CommandLineValue("-prefabGraphBatchRequest");
        if (string.IsNullOrWhiteSpace(requestPath) || !File.Exists(requestPath))
            throw new FileNotFoundException($"PrefabGraph batch request was not found: {requestPath}");
        var batch = JsonUtility.FromJson<BatchCompileRequest>(File.ReadAllText(requestPath));
        if (batch == null || batch.requests == null || batch.requests.Length == 0)
            throw new InvalidOperationException("PrefabGraph batch request is empty.");
        var failures = new List<string>();
        foreach (var item in batch.requests)
        {
            try
            {
                var result = Compile(item.graph_path, item.output_prefab_path);
                WriteResult(item.result_path, result);
            }
            catch (Exception exception)
            {
                WriteResult(item.result_path, new CompileResult
                {
                    created_at = DateTime.UtcNow.ToString("o"), status = "error",
                    output_prefab_path = item.output_prefab_path, source_prefab_read = false,
                    generated_material_paths = Array.Empty<string>(), generated_texture_paths = Array.Empty<string>(),
                    bound_texture_paths = Array.Empty<string>(),
                    generated_shader_names = Array.Empty<string>(), material_template_paths = Array.Empty<string>(),
                    material_texture_readbacks = Array.Empty<MaterialTextureReadback>(), planned_texture_readback_match = false,
                    error = $"{exception.GetType().Name}: {exception.Message}",
                });
                failures.Add($"{item.output_prefab_path}: {exception.Message}");
            }
        }
        if (failures.Count > 0)
            throw new InvalidOperationException($"PrefabGraph batch has {failures.Count} failures: {string.Join(" | ", failures)}");
        Debug.Log($"PrefabGraph batch compiled {batch.requests.Length} no-parent candidates.");
    }

    private static CompileResult Compile(string graphPath, string outputPrefabPath)
    {
        if (string.IsNullOrWhiteSpace(graphPath) || !File.Exists(graphPath))
            throw new FileNotFoundException($"PrefabGraph JSON was not found: {graphPath}");
        if (string.IsNullOrWhiteSpace(outputPrefabPath) || !outputPrefabPath.StartsWith("Assets/", StringComparison.Ordinal))
            throw new InvalidOperationException("PrefabGraph output must be a project-relative Assets/*.prefab path.");
        if (!outputPrefabPath.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("PrefabGraph output must end with .prefab.");

        var graph = JsonUtility.FromJson<Graph>(File.ReadAllText(graphPath));
        ValidateGraph(graph);
        EnsureAssetFolder(Path.GetDirectoryName(outputPrefabPath)?.Replace('\\', '/'));
        if (AssetDatabase.LoadAssetAtPath<GameObject>(outputPrefabPath) != null)
            throw new InvalidOperationException($"Refusing to overwrite an existing Prefab: {outputPrefabPath}");

        var objects = new Dictionary<string, GameObject>(StringComparer.Ordinal);
        var generatedMaterials = new List<string>();
        var generatedTextures = new List<string>();
        var boundTextures = new List<string>();
        var generatedShaders = new List<string>();
        var materialTemplates = new List<string>();
        GameObject root = null;
        try
        {
            foreach (var node in graph.nodes.OrderBy(value => value.depth).ThenBy(value => value.sibling_index))
            {
                var hasParticleSystem = node.component_types != null
                    && node.component_types.Contains("UnityEngine.ParticleSystem");
                // Construct ParticleSystem with its GameObject so the native module handles are initialized before configuration.
                var gameObject = hasParticleSystem
                    ? new GameObject(node.name, typeof(ParticleSystem))
                    : new GameObject(node.name);
                if (!string.IsNullOrWhiteSpace(node.parent_node_id))
                {
                    if (!objects.TryGetValue(node.parent_node_id, out var parent))
                        throw new InvalidOperationException($"Parent node has not been created: {node.parent_node_id}");
                    gameObject.transform.SetParent(parent.transform, false);
                    gameObject.transform.SetSiblingIndex(node.sibling_index);
                }
                else
                {
                    if (root != null)
                        throw new InvalidOperationException("PrefabGraph contains multiple roots.");
                    root = gameObject;
                }
                ApplyTransform(gameObject.transform, node.transform);
                objects.Add(node.node_id, gameObject);
            }

            foreach (var particle in graph.components.particle_systems ?? Array.Empty<ParticleComponent>())
            {
                if (!objects.TryGetValue(particle.node_id, out var target))
                    throw new InvalidOperationException($"ParticleSystem references an unknown node: {particle.node_id}");
                var system = target.GetComponent<ParticleSystem>();
                if (system == null)
                    throw new InvalidOperationException($"ParticleSystem node was not constructed with its native component: {particle.node_id}");
                ConfigureParticleSystem(system, particle.parameters);
                var renderer = target.GetComponent<ParticleSystemRenderer>();
                if (renderer == null)
                    throw new InvalidOperationException($"ParticleSystemRenderer was not created with ParticleSystem: {particle.node_id}");
                ConfigureParticleRenderer(renderer, particle, outputPrefabPath, graph.graph_id, generatedMaterials, generatedTextures, boundTextures, generatedShaders, materialTemplates);
            }

            foreach (var rendererSpec in graph.components.renderers ?? Array.Empty<RendererComponent>())
            {
                if (!objects.TryGetValue(rendererSpec.node_id, out var target))
                    throw new InvalidOperationException($"Renderer references an unknown node: {rendererSpec.node_id}");
                var renderer = target.GetComponent<ParticleSystemRenderer>();
                if (renderer == null)
                    throw new InvalidOperationException($"Only ParticleSystemRenderer is supported in particle_v1: {rendererSpec.node_id}");
                renderer.enabled = rendererSpec.enabled;
                if (rendererSpec.parameters != null)
                {
                    renderer.sortingOrder = rendererSpec.parameters.sorting_order;
                    ConfigureActiveVertexStreams(renderer, rendererSpec.parameters.active_vertex_streams);
                }
            }

            if (root == null || !objects.ContainsKey(graph.root_node_id))
                throw new InvalidOperationException("PrefabGraph root was not created.");
            foreach (var node in graph.nodes)
                objects[node.node_id].SetActive(node.active_self);
            var saved = PrefabUtility.SaveAsPrefabAsset(root, outputPrefabPath);
            if (saved == null)
                throw new InvalidOperationException($"Unity did not save PrefabGraph output: {outputPrefabPath}");
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            var textureReadbacks = CaptureMaterialTextureReadbacks(outputPrefabPath);
            var readbackTexturePaths = new HashSet<string>(textureReadbacks.Select(value => value.texture_path), StringComparer.OrdinalIgnoreCase);
            var plannedTextureReadbackMatch = boundTextures.All(readbackTexturePaths.Contains);
            if (!plannedTextureReadbackMatch)
                throw new InvalidOperationException($"Saved Prefab did not retain every planned Texture binding: {string.Join(", ", boundTextures.Where(path => !readbackTexturePaths.Contains(path)))}");
            return new CompileResult
            {
                created_at = DateTime.UtcNow.ToString("o"),
                graph_id = graph.graph_id,
                status = "pass",
                output_prefab_path = outputPrefabPath,
                source_prefab_read = false,
                node_count = graph.nodes.Length,
                particle_system_count = graph.components.particle_systems?.Length ?? 0,
                generated_material_paths = generatedMaterials.ToArray(),
                generated_texture_paths = generatedTextures.ToArray(),
                bound_texture_paths = boundTextures.Distinct().OrderBy(value => value).ToArray(),
                generated_shader_names = generatedShaders.ToArray(),
                material_template_paths = materialTemplates.Distinct().OrderBy(value => value).ToArray(),
                material_texture_readbacks = textureReadbacks,
                planned_texture_readback_match = plannedTextureReadbackMatch,
                error = null,
            };
        }
        finally
        {
            if (root != null)
                UnityEngine.Object.DestroyImmediate(root);
        }
    }

    private static void ValidateGraph(Graph graph)
    {
        if (graph == null || graph.schema_version != SchemaVersion)
            throw new InvalidOperationException("Unsupported PrefabGraph schema.");
        if (string.IsNullOrWhiteSpace(graph.graph_id) || graph.nodes == null || graph.nodes.Length == 0)
            throw new InvalidOperationException("PrefabGraph id or nodes are missing.");
        if (graph.reconstruction == null || graph.reconstruction.status != "reconstructable" || graph.reconstruction.compiler_profile != "particle_v1")
            throw new InvalidOperationException("Only reconstructable particle_v1 graphs can be compiled.");
        if (graph.reconstruction.missing_fields != null && graph.reconstruction.missing_fields.Length > 0)
            throw new InvalidOperationException("Reconstructable PrefabGraph cannot contain missing_fields.");
        if (graph.reconstruction.unsupported_components != null && graph.reconstruction.unsupported_components.Length > 0)
            throw new InvalidOperationException("Reconstructable PrefabGraph cannot contain unsupported components.");
        if (graph.condition != null && !string.IsNullOrWhiteSpace(graph.condition.parent_prefab_path))
            throw new InvalidOperationException("No-parent compiler smoke rejects parent_prefab_path.");
        if (graph.components == null)
            throw new InvalidOperationException("PrefabGraph components are missing.");
    }

    private static void ApplyTransform(Transform target, TransformData value)
    {
        if (value == null || value.local_position == null || value.local_position.Length != 3 || value.local_rotation == null || value.local_rotation.Length != 4 || value.local_scale == null || value.local_scale.Length != 3)
            throw new InvalidOperationException("particle_v1 requires complete local transform arrays.");
        target.localPosition = new Vector3(value.local_position[0], value.local_position[1], value.local_position[2]);
        target.localRotation = new Quaternion(value.local_rotation[0], value.local_rotation[1], value.local_rotation[2], value.local_rotation[3]);
        target.localScale = new Vector3(value.local_scale[0], value.local_scale[1], value.local_scale[2]);
    }

    private static void ConfigureParticleSystem(ParticleSystem system, ParticleParameters parameters)
    {
        if (parameters == null)
            throw new InvalidOperationException("ParticleSystem parameters are missing.");
        var main = system.main;
        main.loop = parameters.looping;
        main.duration = Mathf.Max(0.05f, parameters.duration_seconds);
        main.startDelay = Mathf.Max(0f, parameters.start_delay_max);
        main.simulationSpace = ParseSimulationSpace(parameters.simulation_space);
        main.maxParticles = Mathf.Max(1, parameters.max_particles);
        main.startLifetime = Mathf.Max(0.01f, parameters.start_lifetime_max);
        main.startSpeed = parameters.start_speed_max;
        main.startSize3D = parameters.start_size_3d;
        if (main.startSize3D)
        {
            main.startSizeX = Mathf.Max(0.001f, parameters.start_size_x_max);
            main.startSizeY = Mathf.Max(0.001f, parameters.start_size_y_max);
            main.startSizeZ = Mathf.Max(0.001f, parameters.start_size_z_max);
        }
        else
        {
            main.startSize = Mathf.Max(0.001f, parameters.start_size_max);
        }
        main.startRotation = parameters.start_rotation_max;
        main.gravityModifier = parameters.gravity_modifier_max;
        var startColor = ParseColor(parameters.start_color_rgba, Color.white);
        main.startColor = startColor;

        var emission = system.emission;
        emission.enabled = parameters.emission_enabled;
        emission.rateOverTime = Mathf.Max(0f, parameters.emission_rate_over_time_max);
        emission.SetBursts(parameters.burst_particle_count > 0
            ? new[] { new ParticleSystem.Burst(0f, (short)Mathf.Clamp(parameters.burst_particle_count, 1, short.MaxValue)) }
            : Array.Empty<ParticleSystem.Burst>());

        var shape = system.shape;
        shape.enabled = parameters.shape_enabled;
        if (shape.enabled)
        {
            shape.shapeType = ParseShape(parameters.shape_type);
            shape.radius = Mathf.Max(0f, parameters.shape_radius);
        }

        var colorOverLifetime = system.colorOverLifetime;
        colorOverLifetime.enabled = parameters.color_over_lifetime_enabled;
        if (colorOverLifetime.enabled)
        {
            var gradient = EffectDemoParticleColorGradient.HasData(parameters.color_over_lifetime_gradient)
                ? parameters.color_over_lifetime_gradient.ToUnity()
                : new Gradient();
            if (!EffectDemoParticleColorGradient.HasData(parameters.color_over_lifetime_gradient))
                gradient.SetKeys(
                    new[] { new GradientColorKey(startColor, 0f), new GradientColorKey(ParseColor(parameters.end_color_rgba, startColor), 1f) },
                    new[] { new GradientAlphaKey(startColor.a, 0f), new GradientAlphaKey(ParseColor(parameters.end_color_rgba, Color.clear).a, 1f) });
            colorOverLifetime.color = gradient;
        }

        var sizeOverLifetime = system.sizeOverLifetime;
        sizeOverLifetime.enabled = parameters.size_over_lifetime_enabled;
        if (sizeOverLifetime.enabled)
            sizeOverLifetime.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 1f, 1f, Mathf.Max(0f, parameters.end_size_multiplier)));
    }

    private static void ConfigureParticleRenderer(ParticleSystemRenderer renderer, ParticleComponent component, string outputPrefabPath, string graphId, List<string> generatedMaterials, List<string> generatedTextures, List<string> boundTextures, List<string> generatedShaders, List<string> materialTemplates)
    {
        var colorMode = component.parameters?.material_color_mode;
        if (!string.IsNullOrEmpty(colorMode) && colorMode != "legacy_start_color" && colorMode != "preserve_template")
            throw new InvalidOperationException("Unsupported material_color_mode: " + colorMode);
        renderer.renderMode = ParseRenderMode(component.parameters?.renderer_mode);
        renderer.sortingOrder = component.parameters?.sorting_order ?? 0;
        var meshPaths = component.mesh_paths ?? Array.Empty<string>();
        if (renderer.renderMode == ParticleSystemRenderMode.Mesh)
        {
            if (meshPaths.Length == 0)
                throw new InvalidOperationException($"Mesh particle renderer requires mesh_paths: {component.node_id}");
            renderer.mesh = LoadFirstMesh(meshPaths[0]);
        }
        var materialPaths = component.material_paths ?? Array.Empty<string>();
        var projectMaterialPaths = materialPaths.Where(path => !IsBuiltinAssetPath(path)).ToArray();
        if (projectMaterialPaths.Length > 0)
        {
            var material = AssetDatabase.LoadAssetAtPath<Material>(projectMaterialPaths[0]);
            if (material == null)
                throw new FileNotFoundException($"Particle material could not be loaded: {projectMaterialPaths[0]}");
            renderer.sharedMaterial = material;
            return;
        }

        var prefabFolder = Path.GetDirectoryName(outputPrefabPath)?.Replace('\\', '/');
        var materialFolder = $"{prefabFolder}/Materials";
        EnsureAssetFolder(materialFolder);
        var materialPath = $"{materialFolder}/{graphId}_{component.component_id}.mat";
        if (AssetDatabase.LoadAssetAtPath<Material>(materialPath) != null)
            throw new InvalidOperationException($"Refusing to overwrite generated material: {materialPath}");
        var useGeneratedSoftShader = string.Equals(component.parameters?.shader_profile, "generated_soft", StringComparison.Ordinal);
        var defaultParticleMaterial = renderer.sharedMaterial;
        var materialTemplatePath = component.parameters?.material_template_path;
        var materialTemplate = string.IsNullOrWhiteSpace(materialTemplatePath)
            ? null
            : AssetDatabase.LoadAssetAtPath<Material>(materialTemplatePath);
        if (!string.IsNullOrWhiteSpace(materialTemplatePath) && materialTemplate == null)
            throw new FileNotFoundException($"Particle material template could not be loaded: {materialTemplatePath}");
        var shader = materialTemplate != null
            ? materialTemplate.shader
            : useGeneratedSoftShader
            ? Shader.Find("VFXGenerated/SoftParticle")
            : defaultParticleMaterial?.shader;
        shader = shader
            ?? Shader.Find("Universal Render Pipeline/Particles/Unlit")
            ?? Shader.Find("Particles/Standard Unlit")
            ?? Shader.Find("Unlit/Color");
        if (shader == null)
            throw new InvalidOperationException("No compatible particle shader was found.");
        var useEngineParticleTemplate = materialTemplate != null || (!useGeneratedSoftShader && defaultParticleMaterial != null && defaultParticleMaterial.shader == shader);
        var generated = materialTemplate != null
            ? new Material(materialTemplate)
            : useEngineParticleTemplate
                ? new Material(defaultParticleMaterial)
                : new Material(shader);
        generated.name = $"{graphId}_{component.component_id}";
        // Missing mode keeps historical Graphs byte-for-byte compatible in meaning.
        if (colorMode != "preserve_template")
        {
            var color = ParseColor(component.parameters?.start_color_rgba, Color.white);
            if (generated.HasProperty("_BaseColor")) generated.SetColor("_BaseColor", color);
            if (generated.HasProperty("_Color")) generated.SetColor("_Color", color);
            if (generated.HasProperty("_Main_Color")) generated.SetColor("_Main_Color", color);
            if (generated.HasProperty("_TintColor")) generated.SetColor("_TintColor", color);
        }
        if (!useEngineParticleTemplate)
            ConfigureTransparentParticleMaterial(generated);
        var textureAssetPath = component.parameters?.texture_asset_path;
        if (!string.IsNullOrWhiteSpace(textureAssetPath))
        {
            if (!textureAssetPath.StartsWith("Assets/", StringComparison.Ordinal))
                throw new InvalidOperationException($"MaterialPlan texture must be a project asset: {textureAssetPath}");
            var texture = AssetDatabase.LoadAssetAtPath<Texture>(textureAssetPath);
            if (texture == null)
                throw new FileNotFoundException($"MaterialPlan texture could not be loaded: {textureAssetPath}");
            var propertyName = component.parameters?.texture_property_name;
            if (string.IsNullOrWhiteSpace(propertyName))
                propertyName = generated.HasProperty("_MainTex") ? "_MainTex" : generated.HasProperty("_BaseMap") ? "_BaseMap" : null;
            if (string.IsNullOrWhiteSpace(propertyName) || !generated.HasProperty(propertyName))
                throw new InvalidOperationException($"Material {generated.name} does not expose planned texture property {propertyName ?? "<none>"}.");
            generated.SetTexture(propertyName, texture);
            boundTextures.Add(textureAssetPath);
        }
        else if (!string.IsNullOrWhiteSpace(component.parameters?.texture_profile))
        {
            var textureProfile = component.parameters.texture_profile;
            var textureFolder = $"{prefabFolder}/Textures";
            EnsureAssetFolder(textureFolder);
            var texturePath = $"{textureFolder}/{graphId}_{component.component_id}_{textureProfile}.asset";
            var texture = CreateParticleTexture(textureProfile);
            AssetDatabase.CreateAsset(texture, texturePath);
            if (generated.HasProperty("_BaseMap"))
                generated.SetTexture("_BaseMap", texture);
            if (generated.HasProperty("_MainTex"))
                generated.SetTexture("_MainTex", texture);
            generatedTextures.Add(texturePath);
            boundTextures.Add(texturePath);
        }
        AssetDatabase.CreateAsset(generated, materialPath);
        renderer.sharedMaterial = generated;
        generatedMaterials.Add(materialPath);
        generatedShaders.Add(shader.name);
        if (materialTemplate != null)
            materialTemplates.Add(materialTemplatePath);
    }

    private static void ConfigureActiveVertexStreams(ParticleSystemRenderer renderer, string[] names)
    {
        if (names == null || names.Length == 0)
            return;
        var streams = new List<ParticleSystemVertexStream>();
        foreach (var name in names)
        {
            if (!Enum.TryParse(name, true, out ParticleSystemVertexStream stream))
                throw new InvalidOperationException($"Unsupported ParticleSystemVertexStream: {name}");
            streams.Add(stream);
        }
        renderer.SetActiveVertexStreams(streams);
    }

    private static void ConfigureTransparentParticleMaterial(Material material)
    {
        if (material == null)
            throw new InvalidOperationException("Generated particle material is missing.");
        var isUrp = material.shader != null && material.shader.name.StartsWith("Universal Render Pipeline/", StringComparison.Ordinal);
        var isGeneratedSoftParticle = material.shader != null && material.shader.name == "VFXGenerated/SoftParticle";
        if (isGeneratedSoftParticle)
            return;
        if (isUrp && material.HasProperty("_Surface"))
            material.SetFloat("_Surface", 1f);
        if (isUrp && material.HasProperty("_Blend"))
            material.SetFloat("_Blend", 0f);
        // Particle Standard Unlit keeps blend fields hidden, so HasProperty may be false even though the shader consumes them.
        material.SetFloat("_SrcBlend", (float)UnityEngine.Rendering.BlendMode.SrcAlpha);
        material.SetFloat("_DstBlend", (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        material.SetFloat("_ZWrite", 0f);
        if (!isUrp)
        {
            material.SetFloat("_Mode", 0f);
            material.DisableKeyword("_ALPHATEST_ON");
            material.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            material.EnableKeyword("_ALPHABLEND_ON");
        }
        material.SetOverrideTag("RenderType", "Transparent");
        material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
        if (isUrp)
            material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
    }

    private static MaterialTextureReadback[] CaptureMaterialTextureReadbacks(string prefabPath)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
        if (prefab == null)
            throw new FileNotFoundException($"Saved Prefab could not be loaded for Material readback: {prefabPath}");
        var records = new List<MaterialTextureReadback>();
        foreach (var renderer in prefab.GetComponentsInChildren<Renderer>(true))
        {
            foreach (var material in renderer.sharedMaterials.Where(value => value != null))
            {
                foreach (var propertyName in material.GetTexturePropertyNames())
                {
                    var texture = material.GetTexture(propertyName);
                    if (texture == null)
                        continue;
                    records.Add(new MaterialTextureReadback
                    {
                        renderer_name = renderer.name,
                        material_path = AssetDatabase.GetAssetPath(material),
                        shader_name = material.shader == null ? null : material.shader.name,
                        property_name = propertyName,
                        texture_path = AssetDatabase.GetAssetPath(texture),
                    });
                }
            }
        }
        return records.OrderBy(value => value.renderer_name, StringComparer.Ordinal).ThenBy(value => value.material_path, StringComparer.Ordinal).ThenBy(value => value.property_name, StringComparer.Ordinal).ToArray();
    }

    private static bool IsBuiltinAssetPath(string path)
    {
        return !string.IsNullOrWhiteSpace(path)
            && (path.StartsWith("Resources/", StringComparison.Ordinal)
                || path.StartsWith("Library/", StringComparison.Ordinal));
    }

    private static ParticleSystemSimulationSpace ParseSimulationSpace(string value)
    {
        return string.Equals(value, "World", StringComparison.OrdinalIgnoreCase)
            ? ParticleSystemSimulationSpace.World
            : ParticleSystemSimulationSpace.Local;
    }

    private static ParticleSystemShapeType ParseShape(string value)
    {
        if (Enum.TryParse(value, true, out ParticleSystemShapeType parsed))
            return parsed;
        throw new InvalidOperationException($"Unsupported ParticleSystem shape: {value}");
    }

    private static ParticleSystemRenderMode ParseRenderMode(string value)
    {
        if (Enum.TryParse(value, true, out ParticleSystemRenderMode parsed))
            return parsed;
        throw new InvalidOperationException($"Unsupported ParticleSystem render mode: {value}");
    }

    private static Mesh LoadFirstMesh(string assetPath)
    {
        if (string.IsNullOrWhiteSpace(assetPath) || !assetPath.StartsWith("Assets/", StringComparison.Ordinal))
            throw new InvalidOperationException($"Particle mesh must be a project asset: {assetPath ?? "<none>"}");
        var direct = AssetDatabase.LoadAssetAtPath<Mesh>(assetPath);
        if (direct != null)
            return direct;
        var mesh = AssetDatabase.LoadAllAssetsAtPath(assetPath).OfType<Mesh>().FirstOrDefault();
        if (mesh == null)
            throw new FileNotFoundException($"Particle mesh could not be loaded: {assetPath}");
        return mesh;
    }

    private static Color ParseColor(float[] values, Color fallback)
    {
        return values != null && values.Length == 4
            ? new Color(values[0], values[1], values[2], values[3])
            : fallback;
    }

    private static Texture2D CreateParticleTexture(string profile)
    {
        var texture = new Texture2D(128, 128, TextureFormat.RGBA32, false, true)
        {
            name = $"Generated_{profile}",
            filterMode = FilterMode.Bilinear,
            wrapMode = TextureWrapMode.Clamp,
        };
        var pixels = new Color[128 * 128];
        for (var y = 0; y < 128; y++)
        {
            for (var x = 0; x < 128; x++)
            {
                var u = (x + 0.5f) / 128f * 2f - 1f;
                var v = (y + 0.5f) / 128f * 2f - 1f;
                var radius = Mathf.Sqrt(u * u + v * v);
                var alpha = profile == "spark"
                    ? Mathf.Clamp01(1f - radius) * Mathf.Clamp01(1f - Mathf.Abs(v) * 1.8f)
                    : Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(1f - radius));
                pixels[y * 128 + x] = new Color(1f, 1f, 1f, alpha);
            }
        }
        texture.SetPixels(pixels);
        texture.Apply(false, true);
        return texture;
    }

    private static void EnsureAssetFolder(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !path.StartsWith("Assets", StringComparison.Ordinal))
            throw new InvalidOperationException($"Invalid asset folder: {path}");
        var parts = path.Split('/');
        var current = parts[0];
        for (var index = 1; index < parts.Length; index++)
        {
            var next = $"{current}/{parts[index]}";
            if (!AssetDatabase.IsValidFolder(next))
                AssetDatabase.CreateFolder(current, parts[index]);
            current = next;
        }
    }

    private static string CommandLineValue(string key)
    {
        var args = Environment.GetCommandLineArgs();
        for (var index = 0; index < args.Length - 1; index++)
        {
            if (string.Equals(args[index], key, StringComparison.OrdinalIgnoreCase))
                return args[index + 1];
        }
        return null;
    }

    private static void WriteResult(string path, CompileResult result)
    {
        if (string.IsNullOrWhiteSpace(path) || result == null)
            return;
        var parent = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(parent))
            Directory.CreateDirectory(parent);
        File.WriteAllText(path, JsonUtility.ToJson(result, true) + "\n");
    }
}
