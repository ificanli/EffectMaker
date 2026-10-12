using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;

[DefaultExecutionOrder(32000)]
public sealed class EffectDemoMaterialTrajectoryExecutor : MonoBehaviour
{
    public const string RequestSchema = "effectdemo_material_trajectory_requests.v1";
    public const string SpecSchema = "material_trajectory_spec.v1";
    public const string ResultSchema = "material_trajectory_execution_result.v1";

    [Serializable]
    public sealed class RequestManifest
    {
        public string schema_version;
        public string run_id;
        public int width = 512;
        public int height = 512;
        public int target_intervals = 10;
        public string run_resource_audit_path;
        public RequestItem[] requests;
    }

    [Serializable]
    public sealed class RequestItem
    {
        public string trajectory_id;
        public string spec_path;
        public string capture_dir;
        public string material_timeline_path;
        public string result_path;
        public string prefab_path;
        public string context_renderer_status;
        public string context_renderer_reason;
        public TrackClamp[] track_clamps;
        public bool has_negative_mutation;
    }

    [Serializable]
    public sealed class TrackClamp
    {
        public bool has_min;
        public float min;
        public bool has_max;
        public float max;
    }

    [Serializable]
    public sealed class MaterialTrajectorySpec
    {
        public string schema_version;
        public string trajectory_id;
        public string curriculum_id;
        public int seed;
        public string category;
        public string label;
        public SourceAsset source_asset;
        public StyleProfile style_profile;
        public string control_scope;
        public float duration_seconds;
        public ParameterTrack[] parameter_tracks;
        public ParticleColorTrack[] particle_color_tracks;
        public MaterialPropertyTrack[] material_property_tracks;
        public KeywordEvent[] keyword_events;
        public TextureSwapEvent[] texture_swap_events;
        public MaterialReplaceEvent[] material_replace_events;
        public string[] expected_signals;
        public NegativeMutation negative_mutation;
        public bool has_negative_mutation;
        public SplitGroup split_group;
    }

    [Serializable]
    public sealed class SourceAsset
    {
        public string material_path;
        public string material_name;
        public string shader_name;
        public string shader_path;
        public TextureBinding[] texture_bindings;
        public string[] effect_families;
        public string[] source_categories;
    }

    [Serializable]
    public sealed class TextureBinding
    {
        public string property_name;
        public string texture_path;
        public string[] tags;
    }

    [Serializable]
    public sealed class StyleProfile
    {
        public string family;
        public string[] keywords;
    }

    [Serializable]
    public sealed class ParameterTrack
    {
        public string property_name;
        public string semantic;
        public string value_kind;
        public float[] start_value;
        public float[] end_value;
        public string curve;
        public float start_time_seconds;
        public float duration_seconds;
        public bool has_clamp_min;
        public float clamp_min;
        public bool has_clamp_max;
        public float clamp_max;
    }

    [Serializable]
    public sealed class ParticleColorTrack
    {
        public string target_material_path;
        public float[] start_color;
        public float[] end_color;
        public string curve;
        public float start_time_seconds;
        public float duration_seconds;
        public bool disable_color_over_lifetime;
    }

    [Serializable]
    public sealed class MaterialPropertyTrack
    {
        public string target_material_path;
        public string property_name;
        public string value_kind;
        public float[] start_value;
        public float[] end_value;
        public string curve;
        public float start_time_seconds;
        public float duration_seconds;
    }

    [Serializable]
    public sealed class KeywordEvent
    {
        public float time_seconds;
        public string keyword;
        public bool enabled;
    }

    [Serializable]
    public sealed class TextureSwapEvent
    {
        public float time_seconds;
        public string property_name;
        public string from_texture_path;
        public string to_texture_path;
        public string[] from_tags;
        public string[] to_tags;
    }

    [Serializable]
    public sealed class MaterialReplaceEvent
    {
        public float time_seconds;
        public string from_material_path;
        public string to_material_path;
        public bool same_shader_required;
    }

    [Serializable]
    public sealed class NegativeMutation
    {
        public string type;
        public float severity;
        public string reason;
    }

    [Serializable]
    public sealed class SplitGroup
    {
        public string shader_group;
        public string material_group;
    }

    [Serializable]
    public sealed class PreparedItem
    {
        public RequestItem request;
        public MaterialTrajectorySpec spec;
        public Material source_material;
        public GameObject prefab_asset;
        public PreparedTextureEvent[] texture_events;
        public PreparedMaterialEvent[] material_events;
        public string preparation_error;
        [NonSerialized] public ResourceAudit last_resource_audit;
    }

    [Serializable]
    public sealed class PreparedTextureEvent
    {
        public TextureSwapEvent definition;
        public Texture from_texture;
        public Texture to_texture;
    }

    [Serializable]
    public sealed class PreparedMaterialEvent
    {
        public MaterialReplaceEvent definition;
        public Material from_material;
        public Material to_material;
    }

    [Serializable]
    public sealed class FrameResult
    {
        public int frame_index;
        public float requested_time_seconds;
        public string path;
        public bool valid;
        public int file_size;
    }

    [Serializable]
    public sealed class ResourceAudit
    {
        public int runtime_materials_created;
        public int runtime_materials_destroyed;
        public int runtime_materials_live;
        public int runtime_textures_created;
        public int runtime_textures_destroyed;
        public int runtime_textures_live;
        public string destruction_mode = "UnityEngine.Object.Destroy completed before result write";
    }

    [Serializable]
    public sealed class ExecutionResult
    {
        public string schema_version = ResultSchema;
        public string created_at;
        public string trajectory_id;
        public string curriculum_id;
        public string spec_path;
        public string category;
        public string label;
        public string control_scope;
        public string status;
        public string prefab_path;
        public string context_renderer_status;
        public string context_renderer_reason;
        public string effective_control_scope;
        public float duration_seconds;
        public float sample_interval_seconds;
        public string material_path;
        public string shader_name;
        public string material_timeline_path;
        public FrameResult[] frames;
        public int valid_frame_count;
        public string[] expected_signals;
        public string[] actual_signals;
        public string[] raw_timeline_signals;
        public string[] missing_signals;
        public string[] unexpected_signals;
        public string[] incidental_timeline_signals;
        public string[] curves_executed;
        public int parameter_track_count;
        public int keyword_event_count;
        public int texture_swap_event_count;
        public int material_replace_event_count;
        public int particle_color_target_count;
        public bool negative_mutation_executed;
        public string[] invariant_errors;
        public ResourceAudit resource_audit;
        public string error;
    }

    [Serializable]
    private sealed class RunResourceAudit
    {
        public string schema_version = "material_trajectory_run_resource_audit.v1";
        public string created_at;
        public string run_id;
        public int render_textures_created;
        public int render_textures_destroyed;
        public int render_textures_live;
        public string destruction_mode = "UnityEngine.Object.Destroy completed before Editor exit";
    }

    private sealed class RuntimeCase
    {
        public GameObject Root;
        public Renderer Renderer;
        public Graphic Graphic;
        public Canvas ContextCanvas;
        public GameObject GraphicCaptureProxy;
        public MeshFilter GraphicCaptureProxyFilter;
        public MeshRenderer GraphicCaptureProxyRenderer;
        public Mesh GraphicCaptureProxyMesh;
        public int TargetSlot;
        public Material ActiveMaterial;
        public readonly Dictionary<string, Material> RuntimeMaterialsBySourcePath = new Dictionary<string, Material>(StringComparer.Ordinal);
        public readonly Dictionary<ParticleColorTrack, List<ParticleSystem>> ParticleColorTargets = new Dictionary<ParticleColorTrack, List<ParticleSystem>>();
        public bool ParticleColorChanged;
        public int ParticleColorTargetCount;
        public bool MultiMaterialPropertyChanged;
        public readonly List<Material> RuntimeMaterials = new List<Material>();
        public readonly HashSet<int> AppliedMaterialEvents = new HashSet<int>();
        public bool NegativeMutationExecuted;
        public readonly List<string> InvariantErrors = new List<string>();
        public ResourceAudit Audit;
    }

    [SerializeField] private RequestManifest requestManifest;
    [SerializeField] private PreparedItem[] preparedItems;
    private Camera captureCamera;
    private Light captureLight;
    private RenderTexture renderTarget;
    private Action pendingLateCapture;
    private bool lateCaptureCompleted;
    private Exception lateCaptureException;
    private int renderTexturesCreated;
    private int renderTexturesDestroyed;

    public void Configure(RequestManifest request, PreparedItem[] items)
    {
        requestManifest = request;
        preparedItems = items;
    }

    private IEnumerator Start()
    {
        try
        {
            if (requestManifest == null)
                throw new InvalidOperationException("Material trajectory request state did not survive Play Mode reload.");
            ConfigureCaptureRig();
        }
        catch (Exception exception)
        {
            Debug.LogError($"Material trajectory executor could not start: {exception}");
#if UNITY_EDITOR
            UnityEditor.EditorApplication.Exit(1);
#else
            Application.Quit(1);
#endif
            yield break;
        }
        foreach (var item in preparedItems ?? Array.Empty<PreparedItem>())
            yield return StartCoroutine(RunPreparedSafely(item));

        ReleaseCaptureRig();
        yield return null;
        WriteRunResourceAudit();
        Debug.Log($"EffectDemo material trajectory execution completed: {preparedItems?.Length ?? 0} specs. Run: {requestManifest?.run_id}");
#if UNITY_EDITOR
        UnityEditor.EditorApplication.Exit(0);
#else
        Application.Quit(0);
#endif
    }

    private IEnumerator RunPreparedSafely(PreparedItem item)
    {
        var routine = ExecutePrepared(item);
        while (true)
        {
            bool moved;
            object current = null;
            try
            {
                moved = routine.MoveNext();
                if (moved)
                    current = routine.Current;
            }
            catch (Exception exception)
            {
                (routine as IDisposable)?.Dispose();
                WriteFailure(item, exception);
                yield break;
            }
            if (!moved)
            {
                (routine as IDisposable)?.Dispose();
                yield break;
            }
            yield return current;
        }
    }

    private IEnumerator ExecutePrepared(PreparedItem item)
    {
        if (item == null || item.request == null || item.spec == null)
            throw new InvalidOperationException("Prepared trajectory item is incomplete.");
        if (!string.IsNullOrWhiteSpace(item.preparation_error))
            throw new InvalidOperationException(item.preparation_error);
        if (item.source_material == null || item.source_material.shader == null)
            throw new InvalidOperationException($"Source Material could not be loaded: {item.spec.source_asset?.material_path}");

        var runtime = new RuntimeCase { Audit = new ResourceAudit() };
        item.last_resource_audit = runtime.Audit;
        var recorder = new EffectDemoMaterialStateRecorder();
        var timelineRequest = TimelineRequest(item);
        var timeline = recorder.CreateTimeline(timelineRequest);
        timeline.capture_order = "trajectory_apply_at_late_update -> material_snapshot -> camera_render";
        var frames = new List<FrameResult>();
        ExecutionResult result = null;

        try
        {
            ValidatePrepared(item, runtime);
            CreatePreview(item, runtime);
            ResetAndPlay(runtime.Root);
            FrameCamera(runtime.Root, runtime.Renderer, runtime.Graphic);
            Directory.CreateDirectory(item.request.capture_dir);
            var duration = Mathf.Max(0.02f, item.spec.duration_seconds);
            var intervals = Mathf.Max(1, requestManifest.target_intervals);
            var sampleInterval = duration / intervals;

            for (var index = 0; index <= intervals; index++)
            {
                if (index > 0 && item.prefab_asset != null)
                    yield return new WaitForSecondsRealtime(sampleInterval);
                var requestedTime = index == intervals ? duration : (float)Math.Round(index * sampleInterval, 4);
                var frameName = $"frame_{index:000}_{requestedTime:0.000}".Replace('.', '_') + ".png";
                var framePath = Path.Combine(item.request.capture_dir, frameName);
                FrameResult captured = null;
                var lateCapture = ExecuteAfterLateUpdate(() =>
                {
                    ApplyAtTime(item, runtime, requestedTime);
                    if (runtime.Graphic != null)
                        runtime.Graphic.Rebuild(CanvasUpdate.PreRender);
                    RefreshGraphicCaptureProxy(runtime);
                    recorder.CaptureFrame(runtime.Root, index, requestedTime, requestedTime, frameName);
                    WriteCameraPng(framePath, runtime.Audit, runtime);
                    var info = new FileInfo(framePath);
                    captured = new FrameResult
                    {
                        frame_index = index,
                        requested_time_seconds = requestedTime,
                        path = frameName,
                        valid = info.Exists && info.Length > 0,
                        file_size = info.Exists ? (int)Math.Min(info.Length, int.MaxValue) : 0,
                    };
                });
                while (lateCapture.MoveNext())
                    yield return lateCapture.Current;
                (lateCapture as IDisposable)?.Dispose();
                frames.Add(captured);
            }

            recorder.Complete(timeline);
            result = BuildResult(item, runtime, timeline, frames, sampleInterval);
        }
        finally
        {
            CleanupRuntimeCase(runtime);
        }

        yield return null;
        WriteTimeline(item.request.material_timeline_path, timeline);
        result.resource_audit = runtime.Audit;
        if (result.resource_audit.runtime_materials_live != 0 || result.resource_audit.runtime_textures_live != 0)
        {
            result.status = "fail";
            result.error = "Runtime resource audit reported live Materials or Textures after cleanup.";
        }
        WriteJson(item.request.result_path, result);
    }

    private static void ValidatePrepared(PreparedItem item, RuntimeCase runtime)
    {
        var spec = item.spec;
        if (spec.schema_version != SpecSchema)
            throw new InvalidOperationException($"Unsupported trajectory spec schema: {spec.schema_version}");
        if (!string.Equals(spec.trajectory_id, item.request.trajectory_id, StringComparison.Ordinal))
            throw new InvalidOperationException($"Request/spec trajectory mismatch: {item.request.trajectory_id} != {spec.trajectory_id}");
        if (spec.source_asset == null)
            throw new InvalidOperationException("Trajectory source_asset is missing.");
        foreach (var track in spec.particle_color_tracks ?? Array.Empty<ParticleColorTrack>())
        {
            if (track == null || string.IsNullOrWhiteSpace(track.target_material_path))
                throw new InvalidOperationException("Particle color trajectory has no target material path.");
            if ((track.start_color?.Length ?? 0) != 4 || (track.end_color?.Length ?? 0) != 4)
                throw new InvalidOperationException("Particle color trajectory requires RGBA start and end values.");
            if (track.duration_seconds <= 0f)
                throw new InvalidOperationException("Particle color trajectory duration must be positive.");
        }
        foreach (var track in spec.material_property_tracks ?? Array.Empty<MaterialPropertyTrack>())
        {
            if (track == null || string.IsNullOrWhiteSpace(track.target_material_path) || string.IsNullOrWhiteSpace(track.property_name))
                throw new InvalidOperationException("Material property trajectory has no material path or property name.");
            var componentCount = track.value_kind == "float" || track.value_kind == "int" ? 1 : 4;
            if ((track.start_value?.Length ?? 0) != componentCount || (track.end_value?.Length ?? 0) != componentCount)
                throw new InvalidOperationException("Material property trajectory has an invalid value component count.");
            if (track.duration_seconds <= 0f)
                throw new InvalidOperationException("Material property trajectory duration must be positive.");
        }
        if (!string.Equals(spec.source_asset.shader_name, item.source_material.shader.name, StringComparison.Ordinal))
            runtime.InvariantErrors.Add($"source_shader_mismatch:{spec.source_asset.shader_name}!={item.source_material.shader.name}");
        if (spec.duration_seconds <= 0f || spec.duration_seconds > 8f)
            throw new InvalidOperationException($"Trajectory duration is outside (0, 8]: {spec.duration_seconds}");
        if (spec.control_scope != "material" && spec.control_scope != "renderer_mpb" && spec.control_scope != "slot_mpb")
            throw new InvalidOperationException($"Unsupported control scope: {spec.control_scope}");
        foreach (var materialEvent in item.material_events ?? Array.Empty<PreparedMaterialEvent>())
        {
            if (materialEvent.from_material == null || materialEvent.to_material == null)
                throw new InvalidOperationException("A Material Replace event asset could not be loaded.");
            if (materialEvent.definition.same_shader_required && materialEvent.from_material.shader != materialEvent.to_material.shader)
                runtime.InvariantErrors.Add($"replacement_shader_mismatch:{materialEvent.definition.from_material_path}->{materialEvent.definition.to_material_path}");
        }
        foreach (var textureEvent in item.texture_events ?? Array.Empty<PreparedTextureEvent>())
        {
            if (textureEvent.from_texture == null || textureEvent.to_texture == null)
                throw new InvalidOperationException("A Texture Swap event asset could not be loaded.");
        }
        if (runtime.InvariantErrors.Count > 0)
            throw new InvalidOperationException(string.Join(";", runtime.InvariantErrors));
    }

    private static void CreatePreview(PreparedItem item, RuntimeCase runtime)
    {
        if (item.prefab_asset != null)
        {
            runtime.Root = Instantiate(item.prefab_asset);
            runtime.Root.name = $"PromptComposition_{item.spec.trajectory_id}";
            runtime.Root.SetActive(false);
            var materialPath = item.spec.source_asset?.material_path;
            foreach (var renderer in runtime.Root.GetComponentsInChildren<Renderer>(true)
                .OrderBy(value => value is ParticleSystemRenderer ? 0 : 1))
            {
                var materials = renderer.sharedMaterials;
                for (var slot = 0; slot < materials.Length; slot++)
                {
                    if (materials[slot] == null || !string.Equals(GetAssetPath(materials[slot]), materialPath, StringComparison.Ordinal))
                        continue;
                    runtime.Renderer = renderer;
                    runtime.TargetSlot = slot;
                    break;
                }
                if (runtime.Renderer != null)
                    break;
            }
            if (runtime.Renderer == null)
            {
                foreach (var graphic in runtime.Root.GetComponentsInChildren<Graphic>(true))
                {
                    if (graphic.material == null || !string.Equals(GetAssetPath(graphic.material), materialPath, StringComparison.Ordinal))
                        continue;
                    runtime.Graphic = graphic;
                    runtime.TargetSlot = 0;
                    break;
                }
                if (runtime.Graphic == null)
                    throw new InvalidOperationException($"Prefab has no Renderer or Graphic using source material: {item.request.prefab_path} -> {materialPath}");
                runtime.ContextCanvas = runtime.Graphic.GetComponentInParent<Canvas>(true);
                if (runtime.ContextCanvas == null)
                    runtime.ContextCanvas = runtime.Graphic.gameObject.AddComponent<Canvas>();
                runtime.ContextCanvas.renderMode = RenderMode.WorldSpace;
                runtime.ContextCanvas.pixelPerfect = false;
            }
        }
        else
        {
            runtime.Root = GameObject.CreatePrimitive(PrimitiveType.Quad);
            runtime.Root.name = $"MaterialTrajectoryPreview_{item.spec.trajectory_id}";
            runtime.Root.transform.position = Vector3.zero;
            runtime.Root.transform.localScale = new Vector3(2.4f, 2.4f, 1f);
            var collider = runtime.Root.GetComponent<Collider>();
            if (collider != null)
                Destroy(collider);
            runtime.Renderer = runtime.Root.GetComponent<MeshRenderer>();
        }
        if (item.prefab_asset == null)
            runtime.TargetSlot = 0;
        ResolveParticleColorTargets(item.spec, runtime);
        ResolveMaterialPropertyTargets(item.spec, runtime);
        runtime.ActiveMaterial = GetOrCloneMaterial(item.source_material, runtime);
        AssignTargetMaterial(runtime, runtime.ActiveMaterial);
        ApplyMaterialPropertyTracks(item.spec, runtime, 0f);
        ApplyParticleColorTracks(item.spec, runtime, 0f);
        runtime.Root.SetActive(true);
    }

    private static void ResolveMaterialPropertyTargets(MaterialTrajectorySpec spec, RuntimeCase runtime)
    {
        var targetPaths = new HashSet<string>((spec.material_property_tracks ?? Array.Empty<MaterialPropertyTrack>())
            .Select(track => track.target_material_path), StringComparer.Ordinal);
        if (targetPaths.Count == 0)
            return;
        var found = new HashSet<string>(StringComparer.Ordinal);
        foreach (var renderer in runtime.Root.GetComponentsInChildren<Renderer>(true))
        {
            var materials = renderer.sharedMaterials;
            var changed = false;
            for (var slot = 0; slot < materials.Length; slot++)
            {
                var sourcePath = GetAssetPath(materials[slot]);
                if (string.IsNullOrWhiteSpace(sourcePath) || !targetPaths.Contains(sourcePath))
                    continue;
                materials[slot] = GetOrCloneMaterial(materials[slot], runtime);
                found.Add(sourcePath);
                changed = true;
            }
            if (changed)
                renderer.sharedMaterials = materials;
        }
        var missing = targetPaths.Except(found, StringComparer.Ordinal).FirstOrDefault();
        if (!string.IsNullOrWhiteSpace(missing))
            throw new InvalidOperationException($"Prefab has no Renderer using material property target: {missing}");
    }

    private static void ResolveParticleColorTargets(MaterialTrajectorySpec spec, RuntimeCase runtime)
    {
        foreach (var track in spec.particle_color_tracks ?? Array.Empty<ParticleColorTrack>())
        {
            var targets = runtime.Root.GetComponentsInChildren<ParticleSystem>(true)
                .Where(system => system != null && system.GetComponent<ParticleSystemRenderer>() != null)
                .Where(system => system.GetComponent<ParticleSystemRenderer>().sharedMaterials
                    .Any(material => material != null && string.Equals(GetAssetPath(material), track.target_material_path, StringComparison.Ordinal)))
                .ToList();
            if (targets.Count == 0)
                throw new InvalidOperationException($"Prefab has no ParticleSystem using particle color target material: {track.target_material_path}");
            runtime.ParticleColorTargets[track] = targets;
            runtime.ParticleColorTargetCount += targets.Count;
        }
    }

    private static string GetAssetPath(UnityEngine.Object value)
    {
#if UNITY_EDITOR
        return value == null ? string.Empty : UnityEditor.AssetDatabase.GetAssetPath(value);
#else
        return string.Empty;
#endif
    }

    private static void AssignTargetMaterial(RuntimeCase runtime, Material material)
    {
        if (runtime.Graphic != null)
        {
            if (material != null && material.HasProperty("_MainTex") && runtime.Graphic.mainTexture != null)
                material.SetTexture("_MainTex", runtime.Graphic.mainTexture);
            runtime.Graphic.material = material;
            return;
        }
        var materials = runtime.Renderer.sharedMaterials;
        materials[runtime.TargetSlot] = material;
        runtime.Renderer.sharedMaterials = materials;
    }

    private static Material CloneMaterial(Material source, RuntimeCase runtime)
    {
        var clone = new Material(source) { name = source.name + " [MaterialTrajectoryRuntime]" };
        runtime.RuntimeMaterials.Add(clone);
        runtime.Audit.runtime_materials_created += 1;
        runtime.Audit.runtime_materials_live += 1;
        return clone;
    }

    private static Material GetOrCloneMaterial(Material source, RuntimeCase runtime)
    {
        var sourcePath = GetAssetPath(source);
        if (!string.IsNullOrWhiteSpace(sourcePath) && runtime.RuntimeMaterialsBySourcePath.TryGetValue(sourcePath, out var existing))
            return existing;
        var clone = CloneMaterial(source, runtime);
        if (!string.IsNullOrWhiteSpace(sourcePath))
            runtime.RuntimeMaterialsBySourcePath[sourcePath] = clone;
        return clone;
    }

    private static void ApplyAtTime(PreparedItem item, RuntimeCase runtime, float time)
    {
        ApplyMaterialEvents(item, runtime, time);
        ApplyKeywordEvents(item.spec, runtime, time);
        ApplyTextureEvents(item, runtime, time);
        ApplyParameterTracks(item.spec, runtime, time);
        ApplyMaterialPropertyTracks(item.spec, runtime, time);
        ApplyParticleColorTracks(item.spec, runtime, time);
        UpdateNegativeMutationState(item, runtime, time);
    }

    private static void ApplyParticleColorTracks(MaterialTrajectorySpec spec, RuntimeCase runtime, float time)
    {
        foreach (var track in spec.particle_color_tracks ?? Array.Empty<ParticleColorTrack>())
        {
            if (!runtime.ParticleColorTargets.TryGetValue(track, out var targets))
                continue;
            var local = Mathf.Clamp01((time - track.start_time_seconds) / Mathf.Max(0.0001f, track.duration_seconds));
            var curved = EvaluateCurve(track.curve, local);
            var color = new Color(
                Mathf.LerpUnclamped(track.start_color[0], track.end_color[0], curved),
                Mathf.LerpUnclamped(track.start_color[1], track.end_color[1], curved),
                Mathf.LerpUnclamped(track.start_color[2], track.end_color[2], curved),
                Mathf.LerpUnclamped(track.start_color[3], track.end_color[3], curved));
            foreach (var system in targets)
            {
                var main = system.main;
                main.startColor = new ParticleSystem.MinMaxGradient(color);
                if (track.disable_color_over_lifetime)
                {
                    var colorOverLifetime = system.colorOverLifetime;
                    colorOverLifetime.enabled = false;
                }
            }
            runtime.ParticleColorChanged |= track.start_color.Zip(track.end_color, (start, end) => Mathf.Abs(start - end) > 0.000001f).Any(changed => changed);
        }
    }

    private static void ApplyMaterialPropertyTracks(MaterialTrajectorySpec spec, RuntimeCase runtime, float time)
    {
        foreach (var track in spec.material_property_tracks ?? Array.Empty<MaterialPropertyTrack>())
        {
            if (!runtime.RuntimeMaterialsBySourcePath.TryGetValue(track.target_material_path, out var material))
                continue;
            if (!material.HasProperty(track.property_name))
                throw new InvalidOperationException($"Material property target does not expose {track.property_name}: {track.target_material_path}");
            var local = Mathf.Clamp01((time - track.start_time_seconds) / Mathf.Max(0.0001f, track.duration_seconds));
            var curved = EvaluateCurve(track.curve, local);
            var componentCount = track.value_kind == "float" || track.value_kind == "int" ? 1 : 4;
            var values = new float[componentCount];
            for (var index = 0; index < componentCount; index++)
                values[index] = Mathf.LerpUnclamped(track.start_value[index], track.end_value[index], curved);
            SetMaterialNumeric(material, Shader.PropertyToID(track.property_name), track.value_kind, values);
            runtime.MultiMaterialPropertyChanged |= track.start_value.Zip(track.end_value, (start, end) => Mathf.Abs(start - end) > 0.000001f).Any(changed => changed);
        }
    }

    private static void ApplyMaterialEvents(PreparedItem item, RuntimeCase runtime, float time)
    {
        var events = item.material_events ?? Array.Empty<PreparedMaterialEvent>();
        for (var index = 0; index < events.Length; index++)
        {
            if (time + 0.0001f < events[index].definition.time_seconds || runtime.AppliedMaterialEvents.Contains(index))
                continue;
            runtime.ActiveMaterial = CloneMaterial(events[index].to_material, runtime);
            AssignTargetMaterial(runtime, runtime.ActiveMaterial);
            runtime.AppliedMaterialEvents.Add(index);
        }
    }

    private static void ApplyKeywordEvents(MaterialTrajectorySpec spec, RuntimeCase runtime, float time)
    {
        foreach (var item in spec.keyword_events ?? Array.Empty<KeywordEvent>())
        {
            if (time + 0.0001f < item.time_seconds)
                continue;
            if (item.enabled)
                runtime.ActiveMaterial.EnableKeyword(item.keyword);
            else
                runtime.ActiveMaterial.DisableKeyword(item.keyword);
        }
    }

    private static void ApplyTextureEvents(PreparedItem item, RuntimeCase runtime, float time)
    {
        foreach (var prepared in item.texture_events ?? Array.Empty<PreparedTextureEvent>())
        {
            var texture = time + 0.0001f >= prepared.definition.time_seconds ? prepared.to_texture : prepared.from_texture;
            SetTexture(runtime, item.spec.control_scope, prepared.definition.property_name, texture);
        }
    }

    private static void ApplyParameterTracks(MaterialTrajectorySpec spec, RuntimeCase runtime, float time)
    {
        foreach (var track in spec.parameter_tracks ?? Array.Empty<ParameterTrack>())
        {
            ValidateTrack(track, runtime.ActiveMaterial);
            var local = Mathf.Clamp01((time - track.start_time_seconds) / Mathf.Max(0.0001f, track.duration_seconds));
            var curved = EvaluateCurve(track.curve, local);
            var values = Interpolate(track, curved);
            SetNumeric(runtime, spec.control_scope, track, values);
        }
    }

    private static void UpdateNegativeMutationState(PreparedItem item, RuntimeCase runtime, float time)
    {
        var mutation = item.spec.negative_mutation;
        if (!item.spec.has_negative_mutation)
            return;
        if (mutation.type == "incompatible_texture")
        {
            runtime.NegativeMutationExecuted |= (item.texture_events ?? Array.Empty<PreparedTextureEvent>())
                .Any(value => time + 0.0001f >= value.definition.time_seconds);
            return;
        }
        runtime.NegativeMutationExecuted |= (item.spec.parameter_tracks ?? Array.Empty<ParameterTrack>())
            .Any(track => time + 0.0001f >= track.start_time_seconds);
    }

    public static float EvaluateCurve(string curve, float t)
    {
        t = Mathf.Clamp01(t);
        switch (curve)
        {
            case "linear":
                return t;
            case "ease_in":
                return t * t;
            case "ease_out":
                return 1f - (1f - t) * (1f - t);
            case "smoothstep":
                return t * t * (3f - 2f * t);
            case "step":
                return t < 0.5f ? 0f : 1f;
            case "pulse":
                return Mathf.Sin(Mathf.PI * t);
            default:
                throw new InvalidOperationException($"Unsupported trajectory curve: {curve}");
        }
    }

    private static float[] Interpolate(ParameterTrack track, float t)
    {
        var componentCount = track.value_kind == "float" || track.value_kind == "int" ? 1 : 4;
        if ((track.start_value?.Length ?? 0) < componentCount || (track.end_value?.Length ?? 0) < componentCount)
            throw new InvalidOperationException($"Track {track.property_name} requires {componentCount} values for {track.value_kind}.");
        var values = new float[componentCount];
        for (var index = 0; index < componentCount; index++)
        {
            var value = Mathf.LerpUnclamped(track.start_value[index], track.end_value[index], t);
            if (track.has_clamp_min)
                value = Mathf.Max(track.clamp_min, value);
            if (track.has_clamp_max)
                value = Mathf.Min(track.clamp_max, value);
            values[index] = value;
        }
        return values;
    }

    private static void ValidateTrack(ParameterTrack track, Material material)
    {
        if (track == null || string.IsNullOrWhiteSpace(track.property_name))
            throw new InvalidOperationException("Trajectory contains an empty parameter track.");
        if (!material.HasProperty(track.property_name))
            throw new InvalidOperationException($"Material {material.name} does not expose property {track.property_name}.");
        if (track.value_kind != "float" && track.value_kind != "int" && track.value_kind != "color" && track.value_kind != "vector")
            throw new InvalidOperationException($"Unsupported value kind: {track.value_kind}");
    }

    private static void SetNumeric(RuntimeCase runtime, string scope, ParameterTrack track, float[] values)
    {
        var id = Shader.PropertyToID(track.property_name);
        var effectiveScope = EffectiveControlScope(scope, runtime);
        if (effectiveScope == "material")
        {
            SetMaterialNumeric(runtime.ActiveMaterial, id, track.value_kind, values);
            return;
        }
        var block = new MaterialPropertyBlock();
        if (effectiveScope == "renderer_mpb")
            runtime.Renderer.GetPropertyBlock(block);
        else
            runtime.Renderer.GetPropertyBlock(block, runtime.TargetSlot);
        SetBlockNumeric(block, id, track.value_kind, values);
        if (effectiveScope == "renderer_mpb")
            runtime.Renderer.SetPropertyBlock(block);
        else
            runtime.Renderer.SetPropertyBlock(block, runtime.TargetSlot);
    }

    private static void SetMaterialNumeric(Material material, int id, string kind, float[] values)
    {
        switch (kind)
        {
            case "float": material.SetFloat(id, values[0]); break;
            case "int": material.SetInteger(id, Mathf.RoundToInt(values[0])); break;
            case "color": material.SetColor(id, new Color(values[0], values[1], values[2], values[3])); break;
            case "vector": material.SetVector(id, new Vector4(values[0], values[1], values[2], values[3])); break;
        }
    }

    private static void SetBlockNumeric(MaterialPropertyBlock block, int id, string kind, float[] values)
    {
        switch (kind)
        {
            case "float": block.SetFloat(id, values[0]); break;
            case "int": block.SetInteger(id, Mathf.RoundToInt(values[0])); break;
            case "color": block.SetColor(id, new Color(values[0], values[1], values[2], values[3])); break;
            case "vector": block.SetVector(id, new Vector4(values[0], values[1], values[2], values[3])); break;
        }
    }

    private static void SetTexture(RuntimeCase runtime, string scope, string property, Texture texture)
    {
        if (!runtime.ActiveMaterial.HasProperty(property))
            throw new InvalidOperationException($"Material {runtime.ActiveMaterial.name} does not expose texture property {property}.");
        var id = Shader.PropertyToID(property);
        var effectiveScope = EffectiveControlScope(scope, runtime);
        if (effectiveScope == "material")
        {
            runtime.ActiveMaterial.SetTexture(id, texture);
            return;
        }
        var block = new MaterialPropertyBlock();
        if (effectiveScope == "renderer_mpb")
            runtime.Renderer.GetPropertyBlock(block);
        else
            runtime.Renderer.GetPropertyBlock(block, runtime.TargetSlot);
        block.SetTexture(id, texture);
        if (effectiveScope == "renderer_mpb")
            runtime.Renderer.SetPropertyBlock(block);
        else
            runtime.Renderer.SetPropertyBlock(block, runtime.TargetSlot);
    }

    private static ExecutionResult BuildResult(
        PreparedItem item,
        RuntimeCase runtime,
        EffectDemoMaterialStateRecorder.Timeline timeline,
        List<FrameResult> frames,
        float sampleInterval)
    {
        var raw = (timeline.summary?.signal_counts ?? Array.Empty<EffectDemoMaterialStateRecorder.SignalCount>())
            .Where(signal => signal.count > 0)
            .Select(signal => signal.signal)
            .Distinct(StringComparer.Ordinal)
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
        var actual = ProjectSignals(item.spec, runtime, raw);
        var expected = AdaptExpectedSignals(item.spec.expected_signals, runtime);
        var missing = expected.Except(actual, StringComparer.Ordinal).OrderBy(value => value, StringComparer.Ordinal).ToArray();
        var unexpected = actual.Except(expected, StringComparer.Ordinal).OrderBy(value => value, StringComparer.Ordinal).ToArray();
        var incidental = raw.Except(actual, StringComparer.Ordinal).OrderBy(value => value, StringComparer.Ordinal).ToArray();
        var validFrames = frames.Count(frame => frame != null && frame.valid);
        var passed = missing.Length == 0 && unexpected.Length == 0 && runtime.InvariantErrors.Count == 0 && validFrames == frames.Count;
        return new ExecutionResult
        {
            created_at = DateTime.UtcNow.ToString("o"),
            trajectory_id = item.spec.trajectory_id,
            curriculum_id = item.spec.curriculum_id,
            spec_path = item.request.spec_path,
            category = item.spec.category,
            label = item.spec.label,
            control_scope = item.spec.control_scope,
            status = passed ? "pass" : "fail",
            prefab_path = item.request.prefab_path,
            context_renderer_status = item.request.context_renderer_status,
            context_renderer_reason = item.request.context_renderer_reason,
            effective_control_scope = EffectiveControlScope(item.spec.control_scope, runtime),
            duration_seconds = item.spec.duration_seconds,
            sample_interval_seconds = sampleInterval,
            material_path = item.spec.source_asset.material_path,
            shader_name = item.source_material.shader.name,
            material_timeline_path = item.request.material_timeline_path,
            frames = frames.ToArray(),
            valid_frame_count = validFrames,
            expected_signals = expected,
            actual_signals = actual,
            raw_timeline_signals = raw,
            missing_signals = missing,
            unexpected_signals = unexpected,
            incidental_timeline_signals = incidental,
            curves_executed = (item.spec.parameter_tracks ?? Array.Empty<ParameterTrack>()).Select(track => track.curve)
                .Concat((item.spec.particle_color_tracks ?? Array.Empty<ParticleColorTrack>()).Select(track => track.curve))
                .Concat((item.spec.material_property_tracks ?? Array.Empty<MaterialPropertyTrack>()).Select(track => track.curve))
                .Distinct().OrderBy(value => value, StringComparer.Ordinal).ToArray(),
            parameter_track_count = item.spec.parameter_tracks?.Length ?? 0,
            keyword_event_count = item.spec.keyword_events?.Length ?? 0,
            texture_swap_event_count = item.spec.texture_swap_events?.Length ?? 0,
            material_replace_event_count = item.spec.material_replace_events?.Length ?? 0,
            particle_color_target_count = runtime.ParticleColorTargetCount,
            negative_mutation_executed = runtime.NegativeMutationExecuted,
            invariant_errors = runtime.InvariantErrors.ToArray(),
            resource_audit = runtime.Audit,
            error = passed ? null : "Expected and projected actual signals differ, a frame is invalid, or an invariant failed.",
        };
    }

    private static string[] ProjectSignals(MaterialTrajectorySpec spec, RuntimeCase runtime, string[] rawSignals)
    {
        var raw = new HashSet<string>(rawSignals, StringComparer.Ordinal);
        var projected = new HashSet<string>(StringComparer.Ordinal);
        var effectiveTracks = (spec.parameter_tracks ?? Array.Empty<ParameterTrack>()).Where(TrackCanChange).ToArray();
        if (effectiveTracks.Length > 0)
        {
            var scopeSignal = ScopeSignal(EffectiveControlScope(spec.control_scope, runtime));
            if (raw.Contains(scopeSignal))
                projected.Add(scopeSignal);
            if (effectiveTracks.Any(track => string.Equals(track.semantic, "dissolve", StringComparison.Ordinal)) && raw.Contains("dissolve_parameter_changed"))
                projected.Add("dissolve_parameter_changed");
        }
        if ((spec.keyword_events?.Length ?? 0) > 0 && raw.Contains("shader_keywords_changed"))
            projected.Add("shader_keywords_changed");
        if ((spec.texture_swap_events?.Length ?? 0) > 0 && raw.Contains("texture_changed"))
            projected.Add("texture_changed");
        if ((spec.material_replace_events?.Length ?? 0) > 0 && raw.Contains("material_instance_replaced"))
            projected.Add("material_instance_replaced");
        if ((spec.particle_color_tracks?.Length ?? 0) > 0 && runtime.ParticleColorChanged)
            projected.Add("particle_color_changed");
        if ((spec.material_property_tracks?.Length ?? 0) > 0 && runtime.MultiMaterialPropertyChanged)
            projected.Add("multi_material_property_changed");
        if (spec.has_negative_mutation && runtime.NegativeMutationExecuted)
            projected.Add("negative_trajectory");
        return projected.OrderBy(value => value, StringComparer.Ordinal).ToArray();
    }

    private static string[] AdaptExpectedSignals(string[] expected, RuntimeCase runtime)
    {
        if (runtime == null || runtime.Graphic == null)
            return (expected ?? Array.Empty<string>()).Distinct(StringComparer.Ordinal).OrderBy(value => value, StringComparer.Ordinal).ToArray();
        return (expected ?? Array.Empty<string>())
            .Select(signal => signal == "renderer_property_block_changed" || signal == "slot_property_block_changed"
                ? "material_property_changed"
                : signal)
            .Distinct(StringComparer.Ordinal)
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
    }

    private static string EffectiveControlScope(string requestedScope, RuntimeCase runtime)
    {
        return runtime != null && runtime.Graphic != null ? "material" : requestedScope;
    }

    private static bool TrackCanChange(ParameterTrack track)
    {
        if (track?.start_value == null || track.end_value == null || track.start_value.Length != track.end_value.Length)
            return false;
        for (var index = 0; index < track.start_value.Length; index++)
        {
            if (Mathf.Abs(track.start_value[index] - track.end_value[index]) > 0.000001f)
                return true;
        }
        return false;
    }

    private static string ScopeSignal(string scope)
    {
        switch (scope)
        {
            case "material": return "material_property_changed";
            case "renderer_mpb": return "renderer_property_block_changed";
            case "slot_mpb": return "slot_property_block_changed";
            default: throw new InvalidOperationException($"Unsupported scope: {scope}");
        }
    }

    private static EffectDemoRuntimeCaptureController.RequestItem TimelineRequest(PreparedItem item)
    {
        return new EffectDemoRuntimeCaptureController.RequestItem
        {
            candidate_id = item.spec.trajectory_id,
            prefab_path = string.IsNullOrWhiteSpace(item.request.prefab_path) ? item.spec.source_asset.material_path : item.request.prefab_path,
            capture_dir = item.request.capture_dir,
            material_timeline_path = item.request.material_timeline_path,
            source_script_fidelity = "controlled_material_trajectory_executor",
            ignored_script_dependency_count = 0,
        };
    }

    private static void CleanupRuntimeCase(RuntimeCase runtime)
    {
        foreach (var material in runtime.RuntimeMaterials)
        {
            if (material == null)
                continue;
            Destroy(material);
            runtime.Audit.runtime_materials_destroyed += 1;
            runtime.Audit.runtime_materials_live -= 1;
        }
        runtime.RuntimeMaterials.Clear();
        if (runtime.GraphicCaptureProxyMesh != null)
            Destroy(runtime.GraphicCaptureProxyMesh);
        if (runtime.GraphicCaptureProxy != null)
            Destroy(runtime.GraphicCaptureProxy);
        if (runtime.Root != null)
            Destroy(runtime.Root);
    }

    private static void ResetAndPlay(GameObject root)
    {
        foreach (var system in root.GetComponentsInChildren<ParticleSystem>(true))
        {
            system.Stop(false, ParticleSystemStopBehavior.StopEmittingAndClear);
            system.Clear(false);
            system.Play(false);
        }
        foreach (var component in root.GetComponentsInChildren<MonoBehaviour>(true))
        {
            if (component == null || component.GetType().FullName != "AssetKits.ParticleImage.ParticleImage")
                continue;
            InvokeNoArg(component, "Stop");
            InvokeNoArg(component, "Clear");
            InvokeNoArg(component, "Play");
        }
    }

    private static void InvokeNoArg(MonoBehaviour component, string methodName)
    {
        var method = component.GetType().GetMethod(methodName, Type.EmptyTypes);
        if (method != null)
            method.Invoke(component, null);
    }

    private static void RefreshGraphicCaptureProxy(RuntimeCase runtime)
    {
        if (runtime == null || runtime.Graphic == null)
            return;
        var particles = runtime.Graphic.GetType().GetProperty("particles")?.GetValue(runtime.Graphic, null) as System.Collections.IEnumerable;
        if (particles == null)
            return;
        var particleSnapshot = particles.Cast<object>().ToArray();
        if (particleSnapshot.Length == 0)
        {
            if (runtime.GraphicCaptureProxyRenderer != null)
                runtime.GraphicCaptureProxyRenderer.enabled = false;
            return;
        }
        var helper = new VertexHelper();
        try
        {
            foreach (var particle in particleSnapshot)
            {
                if (particle == null)
                    continue;
                var render = particle.GetType().GetMethod("Render", new[] { typeof(VertexHelper) });
                render?.Invoke(particle, new object[] { helper });
            }
            if (helper.currentVertCount == 0)
            {
                helper.Dispose();
                helper = null;
                if (!BuildParticleFallbackMesh(runtime, particleSnapshot))
                {
                    if (runtime.GraphicCaptureProxyRenderer != null)
                        runtime.GraphicCaptureProxyRenderer.enabled = false;
                    return;
                }
            }
            else
            {
                if (runtime.GraphicCaptureProxyMesh == null)
                {
                    runtime.GraphicCaptureProxyMesh = new Mesh { name = "MaterialTrajectoryGraphicCaptureMesh" };
                    runtime.GraphicCaptureProxyMesh.MarkDynamic();
                }
                helper.FillMesh(runtime.GraphicCaptureProxyMesh);
            }
        }
        finally
        {
            helper?.Dispose();
        }
        if (runtime.GraphicCaptureProxyMesh == null || runtime.GraphicCaptureProxyMesh.vertexCount == 0)
            return;
        if (runtime.GraphicCaptureProxy == null)
        {
            runtime.GraphicCaptureProxy = new GameObject("MaterialTrajectoryGraphicCaptureProxy");
            runtime.GraphicCaptureProxyFilter = runtime.GraphicCaptureProxy.AddComponent<MeshFilter>();
            runtime.GraphicCaptureProxyRenderer = runtime.GraphicCaptureProxy.AddComponent<MeshRenderer>();
        }
        runtime.GraphicCaptureProxy.transform.SetPositionAndRotation(runtime.Graphic.transform.position, runtime.Graphic.transform.rotation);
        runtime.GraphicCaptureProxy.transform.localScale = runtime.Graphic.transform.lossyScale;
        runtime.GraphicCaptureProxyFilter.sharedMesh = runtime.GraphicCaptureProxyMesh;
        runtime.GraphicCaptureProxyRenderer.sharedMaterial = runtime.ActiveMaterial;
        runtime.GraphicCaptureProxyRenderer.enabled = true;
    }

    private static bool BuildParticleFallbackMesh(RuntimeCase runtime, System.Collections.IEnumerable particles)
    {
        var vertices = new List<Vector3>();
        var uvs = new List<Vector2>();
        var colors = new List<Color>();
        var triangles = new List<int>();
        foreach (var particle in particles)
        {
            if (particle == null)
                continue;
            var position = particle.GetType().GetProperty("Position")?.GetValue(particle, null);
            var size = particle.GetType().GetProperty("Size")?.GetValue(particle, null);
            var color = particle.GetType().GetProperty("Color")?.GetValue(particle, null);
            if (!(position is Vector2 particlePosition) || !(size is Vector2 particleSize) || !(color is Color particleColor))
                continue;
            var start = vertices.Count;
            var half = particleSize * 0.5f;
            vertices.Add(new Vector3(particlePosition.x - half.x, particlePosition.y - half.y, 0f));
            vertices.Add(new Vector3(particlePosition.x - half.x, particlePosition.y + half.y, 0f));
            vertices.Add(new Vector3(particlePosition.x + half.x, particlePosition.y + half.y, 0f));
            vertices.Add(new Vector3(particlePosition.x + half.x, particlePosition.y - half.y, 0f));
            uvs.Add(new Vector2(0f, 0f));
            uvs.Add(new Vector2(0f, 1f));
            uvs.Add(new Vector2(1f, 1f));
            uvs.Add(new Vector2(1f, 0f));
            colors.Add(particleColor);
            colors.Add(particleColor);
            colors.Add(particleColor);
            colors.Add(particleColor);
            triangles.Add(start + 0);
            triangles.Add(start + 1);
            triangles.Add(start + 2);
            triangles.Add(start + 0);
            triangles.Add(start + 2);
            triangles.Add(start + 3);
        }
        if (vertices.Count == 0)
            return false;
        if (runtime.GraphicCaptureProxyMesh == null)
        {
            runtime.GraphicCaptureProxyMesh = new Mesh { name = "MaterialTrajectoryGraphicCaptureMesh" };
            runtime.GraphicCaptureProxyMesh.MarkDynamic();
        }
        runtime.GraphicCaptureProxyMesh.Clear();
        runtime.GraphicCaptureProxyMesh.SetVertices(vertices);
        runtime.GraphicCaptureProxyMesh.SetUVs(0, uvs);
        runtime.GraphicCaptureProxyMesh.SetColors(colors);
        runtime.GraphicCaptureProxyMesh.SetTriangles(triangles, 0, true);
        runtime.GraphicCaptureProxyMesh.RecalculateBounds();
        return true;
    }

    private void FrameCamera(GameObject root, Renderer focusRenderer, Graphic focusGraphic)
    {
        if (focusGraphic != null && focusGraphic.enabled && focusGraphic.gameObject.activeInHierarchy)
        {
            if (runtimeCanvasFor(root) != null)
                runtimeCanvasFor(root).worldCamera = captureCamera;
            var rect = focusGraphic.rectTransform;
            var corners = new Vector3[4];
            rect.GetWorldCorners(corners);
            var uiBounds = new Bounds(corners[0], Vector3.zero);
            for (var index = 1; index < corners.Length; index++)
                uiBounds.Encapsulate(corners[index]);
            var normal = focusGraphic.transform.forward;
            if (normal.sqrMagnitude < 0.000001f)
                normal = Vector3.forward;
            normal.Normalize();
            var up = focusGraphic.transform.up;
            if (up.sqrMagnitude < 0.000001f || Mathf.Abs(Vector3.Dot(up.normalized, normal)) > 0.99f)
                up = Vector3.up;
            var width = Vector3.Distance(corners[0], corners[3]);
            var height = Vector3.Distance(corners[0], corners[1]);
            var uiSize = Mathf.Max(0.5f, Mathf.Max(width / captureCamera.aspect, height));
            var uiDistance = Mathf.Max(2f, uiSize / Mathf.Tan(captureCamera.fieldOfView * 0.5f * Mathf.Deg2Rad) * 0.7f);
            captureCamera.transform.position = uiBounds.center - normal * uiDistance;
            captureCamera.transform.rotation = Quaternion.LookRotation(normal, up);
            return;
        }
        var renderers = focusRenderer != null && focusRenderer.enabled && focusRenderer.gameObject.activeInHierarchy
            && focusRenderer.bounds.size.sqrMagnitude > 0.000001f
            ? new[] { focusRenderer }
            : root.GetComponentsInChildren<Renderer>(true).Where(value => value.enabled && value.gameObject.activeInHierarchy).ToArray();
        if (renderers.Length == 0)
            return;
        var bounds = renderers[0].bounds;
        foreach (var renderer in renderers.Skip(1))
            bounds.Encapsulate(renderer.bounds);
        var size = Mathf.Max(0.5f, Mathf.Max(bounds.size.x / captureCamera.aspect, bounds.size.y));
        var distance = Mathf.Max(2f, size / Mathf.Tan(captureCamera.fieldOfView * 0.5f * Mathf.Deg2Rad) * 0.7f + bounds.extents.z);
        captureCamera.transform.position = bounds.center + Vector3.back * distance;
        captureCamera.transform.rotation = Quaternion.LookRotation(Vector3.forward, Vector3.up);
    }

    private static Canvas runtimeCanvasFor(GameObject root)
    {
        return root == null ? null : root.GetComponentInChildren<Canvas>(true);
    }

    private void ConfigureCaptureRig()
    {
        var width = Mathf.Max(64, requestManifest.width);
        var height = Mathf.Max(64, requestManifest.height);
        var cameraObject = new GameObject("MaterialTrajectoryCaptureCamera");
        captureCamera = cameraObject.AddComponent<Camera>();
        captureCamera.clearFlags = CameraClearFlags.SolidColor;
        captureCamera.backgroundColor = new Color(0.015f, 0.02f, 0.035f, 1f);
        captureCamera.fieldOfView = 38f;
        captureCamera.nearClipPlane = 0.01f;
        captureCamera.farClipPlane = 1000f;
        captureCamera.allowHDR = false;
        captureCamera.allowMSAA = false;
        captureCamera.useOcclusionCulling = false;
        captureCamera.aspect = (float)width / height;
        captureCamera.transform.position = new Vector3(0f, 0f, -3.4f);
        captureCamera.transform.rotation = Quaternion.LookRotation(Vector3.forward, Vector3.up);
        renderTarget = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
        renderTarget.Create();
        renderTexturesCreated += 1;
        captureCamera.targetTexture = renderTarget;

        var lightObject = new GameObject("MaterialTrajectoryCaptureLight");
        captureLight = lightObject.AddComponent<Light>();
        captureLight.type = LightType.Directional;
        captureLight.intensity = 1.5f;
        captureLight.color = Color.white;
        captureLight.transform.rotation = Quaternion.Euler(35f, -30f, 0f);
    }

    private void WriteCameraPng(string destination, ResourceAudit audit, RuntimeCase runtime)
    {
        var width = Mathf.Max(64, requestManifest.width);
        var height = Mathf.Max(64, requestManifest.height);
        Directory.CreateDirectory(Path.GetDirectoryName(destination));
        RefreshGraphicCaptureProxy(runtime);
        Canvas.ForceUpdateCanvases();
        if (runtime != null && runtime.GraphicCaptureProxyRenderer != null)
        {
            Shader.SetGlobalFloat("unity_GUIZTestMode", 8f);
        }
        captureCamera.Render();
        var previous = RenderTexture.active;
        RenderTexture.active = renderTarget;
        var texture = new Texture2D(width, height, TextureFormat.RGBA32, false);
        audit.runtime_textures_created += 1;
        audit.runtime_textures_live += 1;
        try
        {
            texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            texture.Apply(false, false);
            File.WriteAllBytes(destination, texture.EncodeToPNG());
        }
        finally
        {
            RenderTexture.active = previous;
            Destroy(texture);
            audit.runtime_textures_destroyed += 1;
            audit.runtime_textures_live -= 1;
        }
    }

    private IEnumerator ExecuteAfterLateUpdate(Action action)
    {
        if (pendingLateCapture != null)
            throw new InvalidOperationException("A trajectory capture is already waiting for LateUpdate.");
        lateCaptureCompleted = false;
        lateCaptureException = null;
        pendingLateCapture = action;
        while (!lateCaptureCompleted)
            yield return null;
        if (lateCaptureException != null)
            throw lateCaptureException;
    }

    private void LateUpdate()
    {
        if (pendingLateCapture == null)
            return;
        var capture = pendingLateCapture;
        pendingLateCapture = null;
        try
        {
            capture();
        }
        catch (Exception exception)
        {
            lateCaptureException = exception;
        }
        finally
        {
            lateCaptureCompleted = true;
        }
    }

    private void ReleaseCaptureRig()
    {
        if (captureCamera != null)
            captureCamera.targetTexture = null;
        RenderTexture.active = null;
        if (renderTarget != null)
        {
            renderTarget.Release();
            Destroy(renderTarget);
            renderTexturesDestroyed += 1;
        }
        if (captureCamera != null)
            Destroy(captureCamera.gameObject);
        if (captureLight != null)
            Destroy(captureLight.gameObject);
    }

    private void WriteRunResourceAudit()
    {
        if (string.IsNullOrWhiteSpace(requestManifest?.run_resource_audit_path))
            return;
        WriteJson(requestManifest.run_resource_audit_path, new RunResourceAudit
        {
            created_at = DateTime.UtcNow.ToString("o"),
            run_id = requestManifest.run_id,
            render_textures_created = renderTexturesCreated,
            render_textures_destroyed = renderTexturesDestroyed,
            render_textures_live = renderTexturesCreated - renderTexturesDestroyed,
        });
    }

    private static void WriteFailure(PreparedItem item, Exception exception)
    {
        if (item?.request == null)
            return;
        var recorder = new EffectDemoMaterialStateRecorder();
        var timeline = item.spec == null ? null : recorder.CreateTimeline(TimelineRequest(item));
        if (timeline != null)
        {
            timeline.capture_order = "trajectory_apply_at_late_update -> material_snapshot -> camera_render";
            recorder.Complete(timeline, $"{exception.GetType().Name}: {exception.Message}");
            WriteTimeline(item.request.material_timeline_path, timeline);
        }
        var spec = item.spec;
        var expected = spec?.expected_signals ?? Array.Empty<string>();
        string shaderName = null;
        try
        {
            if (item.source_material != null && item.source_material.shader != null)
                shaderName = item.source_material.shader.name;
        }
        catch (MissingReferenceException)
        {
            shaderName = null;
        }
        WriteJson(item.request.result_path, new ExecutionResult
        {
            created_at = DateTime.UtcNow.ToString("o"),
            trajectory_id = item.request.trajectory_id,
            curriculum_id = spec?.curriculum_id,
            spec_path = item.request.spec_path,
            category = spec?.category,
            label = spec?.label,
            control_scope = spec?.control_scope,
            status = "error",
            prefab_path = item.request.prefab_path,
            context_renderer_status = item.request.context_renderer_status,
            context_renderer_reason = item.request.context_renderer_reason,
            effective_control_scope = spec?.control_scope,
            duration_seconds = spec?.duration_seconds ?? 0f,
            material_path = spec?.source_asset?.material_path,
            shader_name = shaderName,
            material_timeline_path = item.request.material_timeline_path,
            frames = Array.Empty<FrameResult>(),
            expected_signals = expected,
            actual_signals = Array.Empty<string>(),
            raw_timeline_signals = Array.Empty<string>(),
            missing_signals = expected,
            unexpected_signals = Array.Empty<string>(),
            incidental_timeline_signals = Array.Empty<string>(),
            curves_executed = spec?.parameter_tracks?.Select(track => track.curve).Distinct().ToArray() ?? Array.Empty<string>(),
            parameter_track_count = spec?.parameter_tracks?.Length ?? 0,
            keyword_event_count = spec?.keyword_events?.Length ?? 0,
            texture_swap_event_count = spec?.texture_swap_events?.Length ?? 0,
            material_replace_event_count = spec?.material_replace_events?.Length ?? 0,
            particle_color_target_count = 0,
            invariant_errors = Array.Empty<string>(),
            resource_audit = item.last_resource_audit ?? new ResourceAudit(),
            error = $"{exception.GetType().Name}: {exception.Message}",
        });
        Debug.LogError($"Material trajectory execution failed for {item.request.trajectory_id}: {exception}");
    }

    private static void WriteTimeline(string path, EffectDemoMaterialStateRecorder.Timeline timeline)
    {
        if (string.IsNullOrWhiteSpace(path) || timeline == null)
            return;
        var parent = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(parent))
            Directory.CreateDirectory(parent);
        File.WriteAllText(path, JsonUtility.ToJson(timeline, true) + "\n");
    }

    private static void WriteJson(string path, object payload)
    {
        if (string.IsNullOrWhiteSpace(path))
            return;
        var parent = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(parent))
            Directory.CreateDirectory(parent);
        File.WriteAllText(path, JsonUtility.ToJson(payload, true) + "\n");
    }
}
