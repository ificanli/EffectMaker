using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Playables;

[InitializeOnLoad]
public static class EffectDemoPrefabPlayabilityAudit
{
    // r3 separates serialized empty slots from broken material and shader references.
    private const int AuditRevision = 3;
    private const string FullImportRoot = "Assets/VFXSourceIngest/Trains/Trains_FX_All_001";
    private const string MarkerRelativePath = "Library/VFXSourceIngest/prefab-playability-audit.marker";
    private const string ReportRelativePath = "Library/VFXSourceIngest/prefab-playability-audit.json";
    private const string FullAssetMarkerRelativePath = "Library/VFXTraining/full-prefab-audit.marker";
    private const string FullAssetReportRelativePath = "Library/VFXTraining/full-prefab-audit.json";
    private static readonly float[] SampleTimes = { 0.05f, 0.25f, 0.75f, 1.5f };

    [Serializable]
    private sealed class AuditReport
    {
        public string schema_version = "effectdemo_prefab_structure_audit.v3";
        public string created_at;
        public int audit_revision;
        public string unity_version;
        public string import_root;
        public float[] sample_times_seconds;
        public int prefab_count;
        public int particle_structure_count;
        public int particle_playable_count;
        public int particle_context_required_count;
        public int static_or_contextual_count;
        public int empty_or_invalid_count;
        public int total_particle_system_count;
        public int total_renderer_count;
        public int total_missing_material_slot_count;
        public int total_serialized_empty_material_slot_count;
        public int total_missing_shader_count;
        public int total_missing_script_count;
        public PrefabRecord[] prefabs;
    }

    [Serializable]
    private sealed class PrefabRecord
    {
        public string prefab_path;
        public string status;
        public string[] reasons;
        public int node_count;
        public int particle_system_count;
        public int particle_renderer_count;
        public int renderer_count;
        public int material_slot_count;
        public int missing_material_slot_count;
        public int serialized_empty_material_slot_count;
        public int missing_shader_count;
        public int missing_script_count;
        public int max_particle_count;
        public float estimated_duration_seconds;
        public bool looping;
        public int animator_count;
        public int legacy_animation_count;
        public int playable_director_count;
        public NodeRecord[] nodes;
        public ParticleRecord[] particle_systems;
        public RendererRecord[] renderers;
        public AnimationRecord[] animations;
    }

    [Serializable]
    private sealed class NodeRecord
    {
        public string hierarchy_path;
        public bool active_self;
        public string[] component_types;
    }

    [Serializable]
    private sealed class ParticleRecord
    {
        public string hierarchy_path;
        public float duration_seconds;
        public bool looping;
        public bool prewarm;
        public int max_particles;
        public string simulation_space;
        public float start_delay_max;
        public float start_lifetime_max;
        public float start_speed_max;
        public float start_size_max;
        public float start_rotation_max;
        public string start_color_mode;
        public bool emission_enabled;
        public float emission_rate_over_time_max;
        public float emission_rate_over_distance_max;
        public int burst_count;
        public bool shape_enabled;
        public string shape_type;
        public float shape_radius;
        public float shape_angle;
        public float shape_arc;
        public string[] enabled_modules;
        public string renderer_mode;
        public string renderer_alignment;
        public string renderer_sort_mode;
        public string[] material_paths;
        public string[] mesh_paths;
    }

    [Serializable]
    private sealed class RendererRecord
    {
        public string hierarchy_path;
        public string renderer_type;
        public bool enabled;
        public int material_slot_count;
        public int missing_material_slot_count;
        public int serialized_empty_material_slot_count;
        public int missing_shader_count;
        public string[] material_paths;
        public string[] mesh_paths;
        public string particle_render_mode;
    }

    [Serializable]
    private sealed class AnimationRecord
    {
        public string hierarchy_path;
        public string source_type;
        public string clip_name;
        public float duration_seconds;
        public bool looping;
    }

    static EffectDemoPrefabPlayabilityAudit()
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
            WriteReport(projectRoot, FullImportRoot, ReportRelativePath);
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
        var importRoot = CommandLineValue("-prefabAuditRoot") ?? FullImportRoot;
        var reportPath = CommandLineValue("-prefabAuditReport") ?? ReportRelativePath;
        WriteReport(projectRoot, importRoot, reportPath);
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

    private static void WriteReport(string projectRoot, string importRoot, string reportRelativePath)
    {
        var report = BuildReport(importRoot);
        var reportPath = Path.IsPathRooted(reportRelativePath) ? reportRelativePath : Path.Combine(projectRoot, reportRelativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(reportPath));
        File.WriteAllText(reportPath, JsonUtility.ToJson(report, true) + "\n");
        Debug.Log(
            $"EffectDemo prefab playability audit r{AuditRevision} completed: {report.prefab_count} prefabs, " +
            $"{report.particle_playable_count} particle-playable, {report.particle_context_required_count} context-required, " +
            $"{report.total_particle_system_count} Particle Systems.");
    }

    private static AuditReport BuildReport(string importRoot)
    {
        var records = new List<PrefabRecord>();
        foreach (var guid in AssetDatabase.FindAssets("t:Prefab", new[] { importRoot }))
        {
            var prefabPath = AssetDatabase.GUIDToAssetPath(guid);
            GameObject contents = null;
            try
            {
                contents = PrefabUtility.LoadPrefabContents(prefabPath);
                records.Add(InspectPrefab(prefabPath, contents));
            }
            catch (Exception exception)
            {
                records.Add(new PrefabRecord
                {
                    prefab_path = prefabPath,
                    status = "audit_error",
                    reasons = new[] { exception.GetType().Name, exception.Message },
                    nodes = Array.Empty<NodeRecord>(),
                    particle_systems = Array.Empty<ParticleRecord>(),
                    renderers = Array.Empty<RendererRecord>(),
                    animations = Array.Empty<AnimationRecord>(),
                });
            }
            finally
            {
                if (contents != null)
                    PrefabUtility.UnloadPrefabContents(contents);
            }
        }
        records.Sort((left, right) => string.Compare(left.prefab_path, right.prefab_path, StringComparison.OrdinalIgnoreCase));
        return new AuditReport
        {
            created_at = DateTime.UtcNow.ToString("o"),
            audit_revision = AuditRevision,
            unity_version = Application.unityVersion,
            import_root = importRoot,
            sample_times_seconds = SampleTimes,
            prefab_count = records.Count,
            particle_structure_count = records.Count(record => record.particle_system_count > 0),
            particle_playable_count = records.Count(record => record.status == "particle_playable"),
            particle_context_required_count = records.Count(record => record.status == "particle_context_required"),
            static_or_contextual_count = records.Count(record => record.status == "static_or_contextual"),
            empty_or_invalid_count = records.Count(record => record.status == "empty_or_invalid" || record.status == "audit_error"),
            total_particle_system_count = records.Sum(record => record.particle_system_count),
            total_renderer_count = records.Sum(record => record.renderer_count),
            total_missing_material_slot_count = records.Sum(record => record.missing_material_slot_count),
            total_serialized_empty_material_slot_count = records.Sum(record => record.serialized_empty_material_slot_count),
            total_missing_shader_count = records.Sum(record => record.missing_shader_count),
            total_missing_script_count = records.Sum(record => record.missing_script_count),
            prefabs = records.ToArray(),
        };
    }

    private static PrefabRecord InspectPrefab(string prefabPath, GameObject contents)
    {
        contents.SetActive(true);
        var transforms = contents.GetComponentsInChildren<Transform>(true);
        var systems = contents.GetComponentsInChildren<ParticleSystem>(true);
        var renderers = contents.GetComponentsInChildren<Renderer>(true);
        var missingScripts = transforms.Sum(transform => GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(transform.gameObject));
        var rendererRecords = new List<RendererRecord>();
        var rootSerializedMaterialSlots = ReadSerializedEmptyMaterialSlotCounts(prefabPath);
        var rootRendererIndex = 0;
        foreach (var renderer in renderers)
            rendererRecords.Add(CaptureRenderer(contents.transform, renderer, prefabPath, rootSerializedMaterialSlots, ref rootRendererIndex));
        var rendererRecordArray = rendererRecords.ToArray();
        var serializedEmptyMaterialSlots = rendererRecordArray.Sum(record => record.serialized_empty_material_slot_count);
        var particleRecords = systems.Select(system => CaptureParticle(contents.transform, system)).ToArray();
        var animationRecords = CaptureAnimations(contents.transform, contents);

        var maxParticleCount = 0;
        foreach (var time in SampleTimes)
        {
            foreach (var system in systems)
                system.Simulate(time, false, true, true);
            foreach (var system in systems)
                maxParticleCount = Mathf.Max(maxParticleCount, system.particleCount);
        }

        var missingMaterialSlots = rendererRecordArray.Sum(record => record.missing_material_slot_count);
        var missingShaders = rendererRecordArray.Sum(record => record.missing_shader_count);
        var materialSlots = rendererRecordArray.Sum(record => record.material_slot_count);
        var duration = 0f;
        var looping = false;
        foreach (var system in systems)
        {
            var main = system.main;
            var particleDuration = CurveMaximum(main.startDelay) + main.duration;
            if (!main.loop)
                particleDuration += CurveMaximum(main.startLifetime);
            duration = Mathf.Max(duration, particleDuration);
            looping |= main.loop;
        }
        foreach (var animation in animationRecords)
        {
            duration = Mathf.Max(duration, animation.duration_seconds);
            looping |= animation.looping;
        }

        var reasons = new List<string>();
        if (missingScripts > 0)
            reasons.Add($"missing_scripts:{missingScripts}");
        if (missingMaterialSlots > 0)
            reasons.Add($"missing_material_slots:{missingMaterialSlots}");
        if (missingShaders > 0)
            reasons.Add($"missing_shaders:{missingShaders}");
        if (systems.Length > 0 && maxParticleCount == 0)
            reasons.Add("no_particles_at_0.05_0.25_0.75_1.5_seconds");
        if (systems.Length == 0 && renderers.Length > 0)
            reasons.Add("no_particle_system_static_or_runtime_controlled");
        if (systems.Length == 0 && renderers.Length == 0)
            reasons.Add("no_renderer_or_particle_system");

        var status = "empty_or_invalid";
        if (systems.Length > 0 && maxParticleCount > 0 && missingScripts == 0 && missingMaterialSlots == 0 && missingShaders == 0)
            status = "particle_playable";
        else if (systems.Length > 0)
            status = "particle_context_required";
        else if (renderers.Length > 0)
            status = "static_or_contextual";

        return new PrefabRecord
        {
            prefab_path = prefabPath,
            status = status,
            reasons = reasons.ToArray(),
            node_count = transforms.Length,
            particle_system_count = systems.Length,
            particle_renderer_count = renderers.Count(renderer => renderer is ParticleSystemRenderer),
            renderer_count = renderers.Length,
            material_slot_count = materialSlots,
            missing_material_slot_count = missingMaterialSlots,
            serialized_empty_material_slot_count = serializedEmptyMaterialSlots,
            missing_shader_count = missingShaders,
            missing_script_count = missingScripts,
            max_particle_count = maxParticleCount,
            estimated_duration_seconds = duration,
            looping = looping,
            animator_count = contents.GetComponentsInChildren<Animator>(true).Length,
            legacy_animation_count = contents.GetComponentsInChildren<Animation>(true).Length,
            playable_director_count = contents.GetComponentsInChildren<PlayableDirector>(true).Length,
            nodes = transforms.Select(transform => new NodeRecord
            {
                hierarchy_path = HierarchyPath(contents.transform, transform),
                active_self = transform.gameObject.activeSelf,
                component_types = transform.gameObject.GetComponents<Component>()
                    .Where(component => component != null)
                    .Select(component => component.GetType().FullName)
                    .OrderBy(value => value, StringComparer.Ordinal)
                    .ToArray(),
            }).ToArray(),
            particle_systems = particleRecords,
            renderers = rendererRecordArray,
            animations = animationRecords,
        };
    }

    private static ParticleRecord CaptureParticle(Transform root, ParticleSystem system)
    {
        var main = system.main;
        var emission = system.emission;
        var shape = system.shape;
        var renderer = system.GetComponent<ParticleSystemRenderer>();
        var enabledModules = new List<string>();
        AddModule(enabledModules, "emission", emission.enabled);
        AddModule(enabledModules, "shape", shape.enabled);
        AddModule(enabledModules, "velocity_over_lifetime", system.velocityOverLifetime.enabled);
        AddModule(enabledModules, "limit_velocity_over_lifetime", system.limitVelocityOverLifetime.enabled);
        AddModule(enabledModules, "inherit_velocity", system.inheritVelocity.enabled);
        AddModule(enabledModules, "force_over_lifetime", system.forceOverLifetime.enabled);
        AddModule(enabledModules, "color_over_lifetime", system.colorOverLifetime.enabled);
        AddModule(enabledModules, "color_by_speed", system.colorBySpeed.enabled);
        AddModule(enabledModules, "size_over_lifetime", system.sizeOverLifetime.enabled);
        AddModule(enabledModules, "size_by_speed", system.sizeBySpeed.enabled);
        AddModule(enabledModules, "rotation_over_lifetime", system.rotationOverLifetime.enabled);
        AddModule(enabledModules, "rotation_by_speed", system.rotationBySpeed.enabled);
        AddModule(enabledModules, "external_forces", system.externalForces.enabled);
        AddModule(enabledModules, "noise", system.noise.enabled);
        AddModule(enabledModules, "collision", system.collision.enabled);
        AddModule(enabledModules, "trigger", system.trigger.enabled);
        AddModule(enabledModules, "sub_emitters", system.subEmitters.enabled);
        AddModule(enabledModules, "texture_sheet_animation", system.textureSheetAnimation.enabled);
        AddModule(enabledModules, "lights", system.lights.enabled);
        AddModule(enabledModules, "trails", system.trails.enabled);
        AddModule(enabledModules, "custom_data", system.customData.enabled);
        var materialPaths = renderer == null
            ? Array.Empty<string>()
            : renderer.sharedMaterials.Where(value => value != null).Select(AssetDatabase.GetAssetPath).Where(value => !string.IsNullOrWhiteSpace(value)).Distinct().ToArray();
        return new ParticleRecord
        {
            hierarchy_path = HierarchyPath(root, system.transform),
            duration_seconds = main.duration,
            looping = main.loop,
            prewarm = main.prewarm,
            max_particles = main.maxParticles,
            simulation_space = main.simulationSpace.ToString(),
            start_delay_max = CurveMaximum(main.startDelay),
            start_lifetime_max = CurveMaximum(main.startLifetime),
            start_speed_max = CurveMaximum(main.startSpeed),
            start_size_max = Mathf.Max(CurveMaximum(main.startSize), Mathf.Max(CurveMaximum(main.startSizeX), Mathf.Max(CurveMaximum(main.startSizeY), CurveMaximum(main.startSizeZ)))),
            start_rotation_max = Mathf.Max(CurveMaximum(main.startRotation), Mathf.Max(CurveMaximum(main.startRotationX), Mathf.Max(CurveMaximum(main.startRotationY), CurveMaximum(main.startRotationZ)))),
            start_color_mode = main.startColor.mode.ToString(),
            emission_enabled = emission.enabled,
            emission_rate_over_time_max = CurveMaximum(emission.rateOverTime),
            emission_rate_over_distance_max = CurveMaximum(emission.rateOverDistance),
            burst_count = emission.burstCount,
            shape_enabled = shape.enabled,
            shape_type = shape.enabled ? shape.shapeType.ToString() : "disabled",
            shape_radius = shape.enabled ? shape.radius : 0f,
            shape_angle = shape.enabled ? shape.angle : 0f,
            shape_arc = shape.enabled ? shape.arc : 0f,
            enabled_modules = enabledModules.ToArray(),
            renderer_mode = renderer == null ? "missing" : renderer.renderMode.ToString(),
            renderer_alignment = renderer == null ? "missing" : renderer.alignment.ToString(),
            renderer_sort_mode = renderer == null ? "missing" : renderer.sortMode.ToString(),
            material_paths = materialPaths,
            mesh_paths = renderer == null ? Array.Empty<string>() : ParticleMeshPaths(renderer),
        };
    }

    private static RendererRecord CaptureRenderer(
        Transform root,
        Renderer renderer,
        string prefabPath,
        IReadOnlyList<int> rootSerializedMaterialSlots,
        ref int rootRendererIndex)
    {
        var materials = renderer.sharedMaterials;
        var serializedEmptyMaterialSlots = CountSerializedEmptyMaterialSlots(renderer, prefabPath, rootSerializedMaterialSlots, ref rootRendererIndex);
        var meshPaths = new List<string>();
        var particleRenderer = renderer as ParticleSystemRenderer;
        if (renderer is SkinnedMeshRenderer skinned && skinned.sharedMesh != null)
            meshPaths.Add(AssetDatabase.GetAssetPath(skinned.sharedMesh));
        var filter = renderer.GetComponent<MeshFilter>();
        if (filter != null && filter.sharedMesh != null)
            meshPaths.Add(AssetDatabase.GetAssetPath(filter.sharedMesh));
        if (particleRenderer != null)
            meshPaths.AddRange(ParticleMeshPaths(particleRenderer));
        return new RendererRecord
        {
            hierarchy_path = HierarchyPath(root, renderer.transform),
            renderer_type = renderer.GetType().Name,
            enabled = renderer.enabled,
            material_slot_count = materials.Length,
            missing_material_slot_count = Mathf.Max(0, materials.Count(value => value == null) - serializedEmptyMaterialSlots),
            serialized_empty_material_slot_count = Mathf.Min(materials.Count(value => value == null), serializedEmptyMaterialSlots),
            missing_shader_count = materials.Count(value => value != null && value.shader == null),
            material_paths = materials.Where(value => value != null).Select(AssetDatabase.GetAssetPath).Where(value => !string.IsNullOrWhiteSpace(value)).Distinct().ToArray(),
            mesh_paths = meshPaths.Where(value => !string.IsNullOrWhiteSpace(value)).Distinct().ToArray(),
            particle_render_mode = particleRenderer == null ? null : particleRenderer.renderMode.ToString(),
        };
    }

    private static int CountSerializedEmptyMaterialSlots(
        Renderer renderer,
        string prefabPath,
        IReadOnlyList<int> rootSerializedMaterialSlots,
        ref int rootRendererIndex)
    {
        var sourceRenderer = PrefabUtility.GetCorrespondingObjectFromSource(renderer) as Renderer;
        if (sourceRenderer == null)
        {
            var globalId = GlobalObjectId.GetGlobalObjectIdSlow(renderer);
            var localFileId = (long)globalId.targetObjectId;
            if (localFileId != 0)
                return CountSerializedEmptyMaterialSlots(prefabPath, localFileId);

            if (rootRendererIndex >= rootSerializedMaterialSlots.Count)
                return 0;
            return rootSerializedMaterialSlots[rootRendererIndex++];
        }

        var sourcePath = AssetDatabase.GetAssetPath(sourceRenderer);
        if (string.IsNullOrWhiteSpace(sourcePath))
            return 0;

        var sourceFileId = Unsupported.GetLocalIdentifierInFileForPersistentObject(sourceRenderer);
        if (sourceFileId == 0)
            return 0;

        return CountSerializedEmptyMaterialSlots(sourcePath, (long)sourceFileId);
    }

    private static int CountSerializedEmptyMaterialSlots(string prefabPath, long sourceFileId)
    {
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var absolutePath = Path.Combine(projectRoot, prefabPath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(absolutePath))
            return 0;

        var emptySlots = 0;
        var inMaterials = false;
        var targetComponent = false;
        foreach (var line in File.ReadLines(absolutePath))
        {
            if (line.StartsWith("--- !u!", StringComparison.Ordinal))
            {
                var fileIdMarker = line.IndexOf('&');
                targetComponent = fileIdMarker >= 0
                    && long.TryParse(line.Substring(fileIdMarker + 1).Trim(), out var componentFileId)
                    && componentFileId == sourceFileId;
                inMaterials = false;
                continue;
            }

            if (!targetComponent || !line.StartsWith("  ", StringComparison.Ordinal))
            {
                inMaterials = false;
                continue;
            }

            var trimmed = line.Trim();
            if (trimmed == "m_Materials:")
            {
                inMaterials = true;
                continue;
            }

            if (!inMaterials)
                continue;

            if (line.StartsWith("  - ", StringComparison.Ordinal))
            {
                if (trimmed.StartsWith("- {fileID: 0", StringComparison.Ordinal))
                    emptySlots++;
                continue;
            }

            inMaterials = false;
            return emptySlots;
        }

        return emptySlots;
    }

    private static List<int> ReadSerializedEmptyMaterialSlotCounts(string prefabPath)
    {
        var counts = new List<int>();
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var absolutePath = Path.Combine(projectRoot, prefabPath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(absolutePath))
            return counts;

        var inMaterials = false;
        var currentCount = 0;
        foreach (var line in File.ReadLines(absolutePath))
        {
            if (line.StartsWith("--- !u!", StringComparison.Ordinal))
            {
                if (inMaterials)
                    counts.Add(currentCount);
                inMaterials = false;
                currentCount = 0;
                continue;
            }

            var trimmed = line.Trim();
            if (trimmed == "m_Materials:")
            {
                inMaterials = true;
                currentCount = 0;
                continue;
            }

            if (!inMaterials)
                continue;

            if (line.StartsWith("  - ", StringComparison.Ordinal))
            {
                if (trimmed.StartsWith("- {fileID: 0", StringComparison.Ordinal))
                    currentCount++;
                continue;
            }

            counts.Add(currentCount);
            inMaterials = false;
            currentCount = 0;
        }

        if (inMaterials)
            counts.Add(currentCount);
        return counts;
    }

    private static AnimationRecord[] CaptureAnimations(Transform root, GameObject contents)
    {
        var records = new List<AnimationRecord>();
        foreach (var animator in contents.GetComponentsInChildren<Animator>(true))
        {
            if (animator.runtimeAnimatorController == null)
                continue;
            foreach (var clip in animator.runtimeAnimatorController.animationClips.Distinct())
                records.Add(CreateAnimationRecord(root, animator.transform, "animator", clip.name, clip.length, clip.isLooping));
        }
        foreach (var animation in contents.GetComponentsInChildren<Animation>(true))
        {
            foreach (AnimationState state in animation)
                records.Add(CreateAnimationRecord(root, animation.transform, "legacy_animation", state.name, state.length, state.wrapMode == WrapMode.Loop));
        }
        foreach (var director in contents.GetComponentsInChildren<PlayableDirector>(true))
        {
            var duration = double.IsNaN(director.duration) || double.IsInfinity(director.duration) ? 0f : (float)director.duration;
            records.Add(CreateAnimationRecord(root, director.transform, "playable_director", director.playableAsset == null ? director.name : director.playableAsset.name, duration, director.extrapolationMode == DirectorWrapMode.Loop));
        }
        return records.ToArray();
    }

    private static AnimationRecord CreateAnimationRecord(Transform root, Transform target, string sourceType, string clipName, float duration, bool looping)
    {
        return new AnimationRecord
        {
            hierarchy_path = HierarchyPath(root, target),
            source_type = sourceType,
            clip_name = clipName,
            duration_seconds = duration,
            looping = looping,
        };
    }

    private static string[] ParticleMeshPaths(ParticleSystemRenderer renderer)
    {
        if (renderer.meshCount <= 0)
            return Array.Empty<string>();
        var meshes = new Mesh[renderer.meshCount];
        var count = renderer.GetMeshes(meshes);
        return meshes.Take(count).Where(mesh => mesh != null).Select(AssetDatabase.GetAssetPath).Where(value => !string.IsNullOrWhiteSpace(value)).Distinct().ToArray();
    }

    private static void AddModule(List<string> modules, string name, bool enabled)
    {
        if (enabled)
            modules.Add(name);
    }

    private static float CurveMaximum(ParticleSystem.MinMaxCurve curve)
    {
        switch (curve.mode)
        {
            case ParticleSystemCurveMode.Constant:
                return curve.constant;
            case ParticleSystemCurveMode.TwoConstants:
                return curve.constantMax;
            default:
                return Mathf.Max(curve.constantMax, curve.curveMultiplier);
        }
    }

    private static string HierarchyPath(Transform root, Transform target)
    {
        var segments = new List<string>();
        var current = target;
        while (current != null)
        {
            segments.Add($"{EncodeHierarchyName(current.name)}[{current.GetSiblingIndex()}]");
            if (current == root)
                break;
            current = current.parent;
        }
        segments.Reverse();
        return string.Join("/", segments);
    }

    private static string EncodeHierarchyName(string value)
    {
        return (value ?? string.Empty).Replace("%", "%25").Replace("/", "%2F");
    }
}
