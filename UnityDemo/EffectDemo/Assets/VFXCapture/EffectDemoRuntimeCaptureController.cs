using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.Playables;
using UnityEngine.UI;

[DefaultExecutionOrder(32000)]
public sealed class EffectDemoRuntimeCaptureController : MonoBehaviour
{
    [Serializable]
    public sealed class SamplingConfig
    {
        public int target_intervals = 10;
        public float min_interval_seconds = 0.02f;
        public float max_interval_seconds = 0.1f;
        public float max_duration_seconds = 8f;
        public int short_effect_target_intervals = 20;
        public bool include_zero = true;
        public string[] duration_sources;
    }

    [Serializable]
    public sealed class RequestItem
    {
        public string candidate_id;
        public string random_seed_key;
        public string prefab_path;
        public string capture_dir;
        public string capture_manifest_path;
        public string material_timeline_path;
        public string source_script_fidelity;
        public int ignored_script_dependency_count;
        public int missing_script_count;
        public string capture_category;
        public string forced_camera_view;
        public bool force_orthographic;
        public float forced_orthographic_size;
    }

    [Serializable]
    public sealed class RequestManifest
    {
        public string schema_version;
        public string run_id;
        public string scene;
        public string camera;
        public int width;
        public int height;
        public float[] background_color_rgba;
        public string expected_render_pipeline_type;
        public string sampling_mode;
        public SamplingConfig sampling;
        public RequestItem[] requests;
    }

    [Serializable]
    public sealed class CandidateEntry
    {
        public RequestItem request;
        public GameObject prefab_asset;
        public bool use_material_state_probe_factory;
        public string runtime_factory_id;
    }

    [Serializable]
    private sealed class CaptureFrame
    {
        public float requested_time_seconds;
        public float capture_time_seconds;
        public string path;
        public bool valid;
        public string error;
        public int file_size;
        public int material_timeline_frame_index;
        public int unity_frame_count;
        public float unity_time_seconds;
        public float unity_unscaled_time_seconds;
        public double realtime_since_startup_seconds;
        public float actual_elapsed_seconds;
        public float simulation_elapsed_seconds;
        public float wall_clock_elapsed_seconds;
        public string camera_view;
        public FramePixelMetrics pixel_metrics;
    }

    [Serializable]
    private sealed class FramePixelMetrics
    {
        public float visible_area_ratio;
        public float border_touch_ratio;
        public float center_offset_normalized;
        public float unity_error_magenta_ratio;
        public int unity_error_magenta_pixel_count;
        public float unity_error_magenta_visible_ratio;
        public bool material_render_error;
        public bool near_blank;
        public bool cropped;
    }

    [Serializable]
    private sealed class BoundsEvidence
    {
        public bool found;
        public float[] center;
        public float[] size;
        public int sample_count;
    }

    [Serializable]
    private sealed class CameraCandidateEvidence
    {
        public string view;
        public float[] forward;
        public float[] up;
        public int sample_count;
        public float max_visible_area_ratio;
        public float mean_visible_area_ratio;
        public float max_border_touch_ratio;
        public float mean_center_offset_normalized;
        public float score;
    }

    [Serializable]
    private sealed class CameraSelectionEvidence
    {
        public string mode = "runtime_multiview_pixel_selection";
        public string status;
        public string selected_view;
        public float[] selected_forward;
        public float[] selected_up;
        public string fit_basis;
        public CameraCandidateEvidence[] candidates;
    }

    [Serializable]
    private sealed class RandomSeedEvidence
    {
        public string hierarchy_path;
        public uint random_seed;
    }

    [Serializable]
    private sealed class ContextEvidence
    {
        public string status;
        public bool main_camera_tagged;
        public bool event_system_ready;
        public bool ground_anchor_ready;
        public bool target_anchor_ready;
        public int canvas_count;
        public int ui_graphic_count;
        public int custom_script_count;
        public int controlled_custom_script_count;
        public int unknown_custom_script_count;
        public int disabled_embedded_camera_count;
        public string script_timing_status;
        public string[] limitations;
    }

    [Serializable]
    private sealed class CaptureManifest
    {
        public string schema = "unity-capture-manifest.v1";
        public string capture_pipeline_version = "play_mode_runtime_isolated_multiview.v2";
        public string unity_version;
        public string active_render_pipeline_type;
        public string configured_render_pipeline_type;
        public string render_pipeline_instance_type;
        public string expected_render_pipeline_type;
        public bool render_pipeline_verified;
        public string graphics_device_type;
        public string color_space;
        public float[] background_color_rgba;
        public string particle_seed_key;
        public string capture_category;
        public string created_at;
        public string capture_root;
        public string scene;
        public string effect;
        public string camera;
        public int[] resolution;
        public string editor_status;
        public string capture_mode;
        public string sampling_mode;
        public bool play_requested;
        public bool looping;
        public float unclamped_duration_seconds;
        public float component_duration_seconds;
        public float subject_duration_seconds;
        public bool subject_duration_override;
        public bool duration_clamped;
        public bool custom_script_timing_unknown;
        public float duration_seconds;
        public float sample_interval_seconds;
        public float[] time_points_seconds;
        public string[] sampling_basis;
        public CaptureFrame[] frames;
        public int valid_frame_count;
        public int invalid_frame_count;
        public string render_error;
        public int particle_system_count;
        public string material_timeline_path;
        public int material_timeline_frame_count;
        public int material_change_count;
        public int material_render_error_frame_count;
        public bool has_dynamic_material_state;
        public string material_capture_sync;
        public bool has_unenumerated_property_block_values;
        public string global_shader_state_status;
        public string instance_isolation_mode;
        public int bounds_probe_instance_id;
        public int camera_probe_instance_id;
        public int capture_instance_id;
        public bool distinct_instance_ids;
        public BoundsEvidence accumulated_bounds;
        public BoundsEvidence subject_bounds;
        public CameraSelectionEvidence camera_selection;
        public ContextEvidence context;
        public RandomSeedEvidence[] particle_random_seeds;
        public bool technical_frame_eligible;
        public bool image_sequence_training_eligible;
        public bool full_visual_training_eligible;
        public string visual_evidence_status;
        public string[] visual_evidence_limitations;
    }

    private sealed class DurationPlan
    {
        public float Duration;
        public float UnclampedDuration;
        public float Interval;
        public bool Looping;
        public bool DurationClamped;
        public bool HasCustomScriptTiming;
        public float ComponentDuration;
        public float SubjectDuration;
        public bool SubjectDurationOverride;
        public readonly List<float> Times = new List<float>();
        public readonly List<string> Basis = new List<string>();
    }

    private sealed class CameraView
    {
        public string Name;
        public Vector3 Forward;
        public Vector3 Up;
    }

    private sealed class CameraAccumulator
    {
        public CameraView View;
        public int SampleCount;
        public float MaxVisible;
        public float VisibleSum;
        public float MaxBorderTouch;
        public float CenterOffsetSum;
    }

    private sealed class CandidateRuntimeEvidence
    {
        public int BoundsProbeInstanceId;
        public int CameraProbeInstanceId;
        public int CaptureInstanceId;
        public int BoundsSampleCount;
        public bool BoundsFound;
        public Bounds Bounds;
        public int SubjectBoundsSampleCount;
        public bool SubjectBoundsFound;
        public Bounds SubjectBounds;
        public CameraSelectionEvidence CameraSelection;
        public ContextEvidence Context;
        public RandomSeedEvidence[] Seeds = Array.Empty<RandomSeedEvidence>();
    }

    [SerializeField] private RequestManifest requestManifest;
    [SerializeField] private CandidateEntry[] candidates;
    [SerializeField] private Transform instanceParent;

    private Camera captureCamera;
    private Light captureLight;
    private RenderTexture renderTarget;
    private RenderTexture cameraEvaluationTarget;
    private GameObject contextRoot;
    private Action pendingLateCapture;
    private double pendingLateCaptureNotBeforeSimulationTime;
    private bool lateCaptureCompleted;
    private Exception lateCaptureException;

    public void Configure(RequestManifest request, CandidateEntry[] entries, Transform runtimeInstanceParent)
    {
        requestManifest = request;
        candidates = entries;
        instanceParent = runtimeInstanceParent;
    }

    private IEnumerator Start()
    {
        ConfigureCaptureRig();
        foreach (var candidate in candidates ?? Array.Empty<CandidateEntry>())
            yield return StartCoroutine(RunCandidateSafely(candidate));

        ReleaseCaptureRig();
        Debug.Log($"EffectDemo runtime VFX capture completed: {candidates?.Length ?? 0} candidates. Run: {requestManifest?.run_id}");
        yield return null;
#if UNITY_EDITOR
        UnityEditor.EditorApplication.Exit(0);
#else
        Application.Quit(0);
#endif
    }

    private IEnumerator RunCandidateSafely(CandidateEntry candidate)
    {
        if (candidate == null || candidate.request == null
            || (candidate.prefab_asset == null && !candidate.use_material_state_probe_factory && string.IsNullOrWhiteSpace(candidate.runtime_factory_id)))
        {
            WriteFailure(candidate?.request, "Prefab could not be loaded or instantiated.");
            yield break;
        }

        var routine = CaptureCandidate(candidate);
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
                WriteFailure(candidate.request, $"{exception.GetType().Name}: {exception.Message}");
                yield break;
            }
            if (!moved)
                yield break;
            yield return current;
        }
    }

    private IEnumerator CaptureCandidate(CandidateEntry candidate)
    {
        var request = candidate.request;
        var seedKey = string.IsNullOrWhiteSpace(request.random_seed_key) ? request.candidate_id : request.random_seed_key;
        var recorder = new EffectDemoMaterialStateRecorder();
        var timeline = recorder.CreateTimeline(request);
        Directory.CreateDirectory(request.capture_dir);
        var evidence = new CandidateRuntimeEvidence();
        GameObject boundsProbe = null;
        GameObject cameraProbe = null;
        GameObject captureRoot = null;
        var previousCaptureDeltaTime = Time.captureDeltaTime;
        var captureDeltaTimeChanged = false;
        try
        {
            captureCamera.orthographic = request.force_orthographic || IsOrthographicProfile(request.capture_category);
            EffectDemoDynamicShaderStateTracker.Reset();
            boundsProbe = CreateFreshInstance(candidate);
            evidence.BoundsProbeInstanceId = boundsProbe.GetInstanceID();
            ConfigureInstanceContext(boundsProbe);
            ApplyDeterministicParticleSeeds(boundsProbe, seedKey);
            boundsProbe.SetActive(true);
            ResetAndPlay(boundsProbe);
            var plan = BuildDurationPlan(boundsProbe, request.capture_category);
            evidence.Bounds = new Bounds(boundsProbe.transform.position, Vector3.one);
            evidence.SubjectBounds = new Bounds(boundsProbe.transform.position, Vector3.one);
            AccumulateBounds(boundsProbe, ref evidence.BoundsFound, ref evidence.Bounds);
            AccumulateSubjectBounds(boundsProbe, request.capture_category, ref evidence.SubjectBoundsFound, ref evidence.SubjectBounds);
            evidence.BoundsSampleCount++;
            evidence.SubjectBoundsSampleCount++;
            var elapsed = 0f;
            while (elapsed < plan.Duration - 0.0001f)
            {
                var delta = Mathf.Min(plan.Interval, plan.Duration - elapsed);
                yield return new WaitForSecondsRealtime(delta);
                elapsed += delta;
                AccumulateBounds(boundsProbe, ref evidence.BoundsFound, ref evidence.Bounds);
                AccumulateSubjectBounds(boundsProbe, request.capture_category, ref evidence.SubjectBoundsFound, ref evidence.SubjectBounds);
                evidence.BoundsSampleCount++;
                evidence.SubjectBoundsSampleCount++;
            }
            Destroy(boundsProbe);
            boundsProbe = null;
            yield return null;

            EffectDemoDynamicShaderStateTracker.Reset();
            cameraProbe = CreateFreshInstance(candidate);
            evidence.CameraProbeInstanceId = cameraProbe.GetInstanceID();
            ConfigureInstanceContext(cameraProbe);
            ApplyDeterministicParticleSeeds(cameraProbe, seedKey);
            evidence.CameraSelection = new CameraSelectionEvidence();
            yield return StartCoroutine(EvaluateCameraSelection(cameraProbe, plan, request, evidence));
            Destroy(cameraProbe);
            cameraProbe = null;
            yield return null;

            EffectDemoDynamicShaderStateTracker.Reset();
            captureRoot = CreateFreshInstance(candidate);
            evidence.CaptureInstanceId = captureRoot.GetInstanceID();
            ConfigureInstanceContext(captureRoot);
            evidence.Context = BuildContextEvidence(captureRoot, request, evidence.CameraSelection);
            evidence.Seeds = ApplyDeterministicParticleSeeds(captureRoot, seedKey);
            captureRoot.SetActive(true);
            ResetAndPlay(captureRoot);
            ApplySelectedCamera(evidence, request);

            var frames = new List<CaptureFrame>();
            Time.captureDeltaTime = Mathf.Max(0.001f, plan.Interval);
            captureDeltaTimeChanged = true;
            var captureStartSimulationTime = Time.timeAsDouble;
            var captureStartRealtime = Time.realtimeSinceStartupAsDouble;
            for (var index = 0; index < plan.Times.Count; index++)
            {
                var requestedTime = plan.Times[index];
                var frameName = $"frame_{index:000}_{requestedTime:0.000}".Replace('.', '_') + ".png";
                var framePath = Path.Combine(request.capture_dir, frameName);
                CaptureFrame capturedFrame = null;
                yield return StartCoroutine(ExecuteAfterLateUpdate(() =>
                {
                    var simulationElapsed = (float)(Time.timeAsDouble - captureStartSimulationTime);
                    var wallClockElapsed = (float)(Time.realtimeSinceStartupAsDouble - captureStartRealtime);
                    recorder.CaptureFrame(captureRoot, index, requestedTime, simulationElapsed, frameName);
                    var pixelMetrics = WriteCameraPng(framePath);
                    var info = new FileInfo(framePath);
                    capturedFrame = new CaptureFrame
                    {
                        requested_time_seconds = requestedTime,
                        capture_time_seconds = simulationElapsed,
                        path = frameName,
                        valid = info.Exists && info.Length > 0,
                        error = info.Exists && info.Length > 0 ? null : "capture file is empty",
                        file_size = info.Exists ? (int)Math.Min(info.Length, int.MaxValue) : 0,
                        material_timeline_frame_index = index,
                        unity_frame_count = Time.frameCount,
                        unity_time_seconds = Time.time,
                        unity_unscaled_time_seconds = Time.unscaledTime,
                        realtime_since_startup_seconds = Time.realtimeSinceStartupAsDouble,
                        actual_elapsed_seconds = simulationElapsed,
                        simulation_elapsed_seconds = simulationElapsed,
                        wall_clock_elapsed_seconds = wallClockElapsed,
                        camera_view = evidence.CameraSelection?.selected_view,
                        pixel_metrics = pixelMetrics,
                    };
                }, captureStartSimulationTime + requestedTime));
                frames.Add(capturedFrame);
            }

            recorder.Complete(timeline);
            WriteTimeline(request, timeline);
            WriteManifest(request, plan, frames, captureRoot.GetComponentsInChildren<ParticleSystem>(true).Length, timeline, evidence, null);
            captureRoot.SetActive(false);
            yield return null;
        }
        finally
        {
            if (captureDeltaTimeChanged)
                Time.captureDeltaTime = previousCaptureDeltaTime;
            if (boundsProbe != null) Destroy(boundsProbe);
            if (cameraProbe != null) Destroy(cameraProbe);
            if (captureRoot != null) Destroy(captureRoot);
        }
    }

    private GameObject CreateFreshInstance(CandidateEntry candidate)
    {
        GameObject root;
        if (candidate.use_material_state_probe_factory)
        {
            root = EffectDemoMaterialStateProbeFactory.Create(true);
        }
        else if (!string.IsNullOrWhiteSpace(candidate.runtime_factory_id))
        {
            root = EffectDemoRuntimeCaptureRegressionProbeFactory.Create(candidate.runtime_factory_id, true);
        }
        else
        {
            if (candidate.prefab_asset == null)
                throw new InvalidOperationException($"Prefab asset is unavailable: {candidate.request?.prefab_path}");
            var inactiveStaging = new GameObject("VFXCaptureInactiveStaging");
            inactiveStaging.SetActive(false);
            root = Instantiate(candidate.prefab_asset, inactiveStaging.transform, false);
            root.name = candidate.prefab_asset.name;
            root.SetActive(false);
            root.transform.SetParent(instanceParent, false);
            Destroy(inactiveStaging);
        }
        if (root == null)
            throw new InvalidOperationException($"Could not create a fresh capture instance: {candidate.request?.prefab_path}");
        root.SetActive(false);
        root.transform.SetParent(instanceParent, false);
        return root;
    }

    private void ConfigureInstanceContext(GameObject root)
    {
        foreach (var embeddedCamera in root.GetComponentsInChildren<Camera>(true))
        {
            if (embeddedCamera != captureCamera)
                embeddedCamera.enabled = false;
        }
        foreach (var canvas in root.GetComponentsInChildren<Canvas>(true))
        {
            if (canvas.renderMode == RenderMode.ScreenSpaceOverlay)
                canvas.renderMode = RenderMode.ScreenSpaceCamera;
            if (canvas.renderMode == RenderMode.ScreenSpaceCamera)
            {
                canvas.worldCamera = captureCamera;
                canvas.planeDistance = 1f;
            }
        }
    }

    private ContextEvidence BuildContextEvidence(GameObject root, RequestItem request, CameraSelectionEvidence cameraSelection)
    {
        var canvases = root.GetComponentsInChildren<Canvas>(true);
        var graphics = root.GetComponentsInChildren<Graphic>(true);
        var scripts = root.GetComponentsInChildren<MonoBehaviour>(true)
            .Where(value => value != null && value != this)
            .ToArray();
        var controlledScripts = scripts.OfType<IEffectDemoCaptureTimingProvider>().ToArray();
        var unknownScripts = scripts.Where(value => !(value is IEffectDemoCaptureTimingProvider)).ToArray();
        var limitations = new List<string>();
        var sourceScriptsExcluded = request.ignored_script_dependency_count > 0
            || string.Equals(request.source_script_fidelity, "source_scripts_excluded", StringComparison.Ordinal);
        if (sourceScriptsExcluded)
            limitations.Add("Source runtime scripts were excluded; script-driven material, timing and activation are incomplete.");
        if (request.missing_script_count > 0)
            limitations.Add($"Prefab contains {request.missing_script_count} missing script components.");
        if (unknownScripts.Length > 0)
            limitations.Add("Custom MonoBehaviour timing is not included in component-derived duration and may trigger after the capture window.");
        if (graphics.Length > 0 && canvases.Length == 0)
            limitations.Add("UI Graphic components have no Canvas in the Prefab hierarchy.");
        if (cameraSelection == null || cameraSelection.status != "selected_visible_view")
            limitations.Add("No camera candidate produced independently visible pixels during camera selection.");
        var blocked = sourceScriptsExcluded
            || request.missing_script_count > 0
            || (graphics.Length > 0 && canvases.Length == 0)
            || cameraSelection == null
            || cameraSelection.status != "selected_visible_view";
        return new ContextEvidence
        {
            status = blocked ? "incomplete_context" : "standard_context_ready",
            main_camera_tagged = captureCamera != null && captureCamera.CompareTag("MainCamera"),
            event_system_ready = EventSystem.current != null,
            ground_anchor_ready = GameObject.Find("VFXCaptureGroundAnchor") != null,
            target_anchor_ready = GameObject.Find("VFXCaptureTarget") != null,
            canvas_count = canvases.Length,
            ui_graphic_count = graphics.Length,
            custom_script_count = scripts.Length,
            controlled_custom_script_count = controlledScripts.Length,
            unknown_custom_script_count = unknownScripts.Length,
            disabled_embedded_camera_count = root.GetComponentsInChildren<Camera>(true).Count(value => value != captureCamera && !value.enabled),
            script_timing_status = unknownScripts.Length > 0 ? "custom_script_duration_unbounded" : controlledScripts.Length > 0 ? "controlled_script_duration" : "component_duration_only",
            limitations = limitations.ToArray(),
        };
    }

    private RandomSeedEvidence[] ApplyDeterministicParticleSeeds(GameObject root, string candidateId)
    {
        var result = new List<RandomSeedEvidence>();
        foreach (var system in root.GetComponentsInChildren<ParticleSystem>(true).OrderBy(value => HierarchyPath(root.transform, value.transform), StringComparer.Ordinal))
        {
            var path = HierarchyPath(root.transform, system.transform);
            var seed = StableSeed($"{candidateId}|{path}");
            system.useAutoRandomSeed = false;
            system.randomSeed = seed;
            result.Add(new RandomSeedEvidence { hierarchy_path = path, random_seed = seed });
        }
        return result.ToArray();
    }

    private static uint StableSeed(string value)
    {
        unchecked
        {
            uint hash = 2166136261;
            foreach (var character in value ?? string.Empty)
            {
                hash ^= character;
                hash *= 16777619;
            }
            return hash == 0 ? 1u : hash;
        }
    }

    private static string HierarchyPath(Transform root, Transform target)
    {
        if (target == root)
            return root.name;
        var parts = new List<string>();
        var current = target;
        while (current != null)
        {
            parts.Add(current.name);
            if (current == root)
                break;
            current = current.parent;
        }
        parts.Reverse();
        return string.Join("/", parts);
    }

    private IEnumerator EvaluateCameraSelection(GameObject root, DurationPlan plan, RequestItem request, CandidateRuntimeEvidence evidence)
    {
        var captureCategory = request.capture_category;
        var forcedCameraView = request.forced_camera_view;
        var views = CameraViews(root, captureCategory);
        var accumulators = views.Select(view => new CameraAccumulator { View = view }).ToArray();
        var useSubjectBounds = evidence.SubjectBoundsFound;
        var bounds = useSubjectBounds
            ? evidence.SubjectBounds
            : evidence.BoundsFound ? evidence.Bounds : new Bounds(root.transform.position, Vector3.one * 2f);
        var sampleTimes = CameraEvaluationTimes(plan);
        root.SetActive(true);
        ResetAndPlay(root);
        var previousCaptureDeltaTime = Time.captureDeltaTime;
        Time.captureDeltaTime = Mathf.Max(0.001f, plan.Interval);
        var evaluationStartSimulationTime = Time.timeAsDouble;
        try
        {
            foreach (var requestedTime in sampleTimes)
            {
                yield return StartCoroutine(ExecuteAfterLateUpdate(() =>
                {
                    foreach (var accumulator in accumulators)
                    {
                        FrameCamera(bounds, accumulator.View);
                        var metrics = RenderPixelMetrics(cameraEvaluationTarget, false, null);
                        accumulator.SampleCount++;
                        accumulator.MaxVisible = Mathf.Max(accumulator.MaxVisible, metrics.visible_area_ratio);
                        accumulator.VisibleSum += metrics.visible_area_ratio;
                        accumulator.MaxBorderTouch = Mathf.Max(accumulator.MaxBorderTouch, metrics.border_touch_ratio);
                        accumulator.CenterOffsetSum += metrics.center_offset_normalized;
                    }
                }, evaluationStartSimulationTime + requestedTime));
            }
        }
        finally
        {
            Time.captureDeltaTime = previousCaptureDeltaTime;
        }
        root.SetActive(false);
        var records = accumulators.Select(value =>
        {
            var meanVisible = value.VisibleSum / Mathf.Max(1, value.SampleCount);
            var meanCenter = value.CenterOffsetSum / Mathf.Max(1, value.SampleCount);
            var score = value.MaxVisible * 0.55f + meanVisible * 0.45f
                - value.MaxBorderTouch * 0.35f - meanCenter * 0.05f;
            return new CameraCandidateEvidence
            {
                view = value.View.Name,
                forward = Vector(value.View.Forward),
                up = Vector(value.View.Up),
                sample_count = value.SampleCount,
                max_visible_area_ratio = value.MaxVisible,
                mean_visible_area_ratio = meanVisible,
                max_border_touch_ratio = value.MaxBorderTouch,
                mean_center_offset_normalized = meanCenter,
                score = score,
            };
        }).ToArray();
        var selected = string.IsNullOrWhiteSpace(forcedCameraView)
            ? records.OrderByDescending(value => value.score).ThenBy(value => value.view, StringComparer.Ordinal).First()
            : records.FirstOrDefault(value => string.Equals(value.view, forcedCameraView, StringComparison.OrdinalIgnoreCase));
        if (selected == null)
            throw new InvalidOperationException($"Unsupported forced camera view: {forcedCameraView}");
        evidence.CameraSelection = new CameraSelectionEvidence
        {
            mode = string.IsNullOrWhiteSpace(forcedCameraView)
                ? "runtime_multiview_pixel_selection"
                : request.force_orthographic && request.forced_orthographic_size > 0f
                    ? "forced_request_view_fixed_frame"
                    : "forced_request_view",
            status = selected.max_visible_area_ratio >= 0.0005f ? "selected_visible_view" : "no_visible_camera_candidate",
            selected_view = selected.view,
            selected_forward = selected.forward,
            selected_up = selected.up,
            fit_basis = useSubjectBounds ? "subject_bounds" : "accumulated_bounds",
            candidates = records,
        };
    }

    private static float[] CameraEvaluationTimes(DurationPlan plan)
    {
        if (plan.Times.Count == 0)
            return new[] { 0f };
        var indices = new[] { 0, plan.Times.Count / 4, plan.Times.Count / 2, plan.Times.Count * 3 / 4, plan.Times.Count - 1 };
        return indices.Select(index => plan.Times[Mathf.Clamp(index, 0, plan.Times.Count - 1)]).Distinct().OrderBy(value => value).ToArray();
    }

    private static CameraView[] CameraViews(GameObject root, string captureCategory)
    {
        var views = new List<CameraView>
        {
            new CameraView { Name = "front", Forward = Vector3.forward, Up = Vector3.up },
            new CameraView { Name = "side", Forward = Vector3.right, Up = Vector3.up },
            new CameraView { Name = "top", Forward = Vector3.down, Up = Vector3.forward },
        };
        var subjectRenderers = root.GetComponentsInChildren<Renderer>(true)
            .Where(renderer => IsSubjectRenderer(renderer, captureCategory))
            .OrderBy(renderer => HierarchyPath(root.transform, renderer.transform), StringComparer.Ordinal)
            .Take(4)
            .ToArray();
        for (var index = 0; index < subjectRenderers.Length; index++)
        {
            var renderer = subjectRenderers[index];
            AddCameraView(views, $"subject_normal_{index}", renderer.transform.forward, renderer.transform.up);
            AddCameraView(views, $"subject_normal_reverse_{index}", -renderer.transform.forward, renderer.transform.up);
        }
        return views.ToArray();
    }

    private void ApplySelectedCamera(CandidateRuntimeEvidence evidence, RequestItem request)
    {
        var selection = evidence.CameraSelection;
        var view = new CameraView
        {
            Name = selection?.selected_view ?? "front",
            Forward = VectorFromArray(selection?.selected_forward, Vector3.forward),
            Up = VectorFromArray(selection?.selected_up, Vector3.up),
        };
        var bounds = evidence.SubjectBoundsFound
            ? evidence.SubjectBounds
            : evidence.BoundsFound ? evidence.Bounds : new Bounds(Vector3.zero, Vector3.one * 2f);
        FrameCamera(bounds, view);
        if (request != null && request.force_orthographic && request.forced_orthographic_size > 0f)
        {
            captureCamera.orthographic = true;
            captureCamera.orthographicSize = request.forced_orthographic_size;
        }
    }

    private static float[] Vector(Vector3 value)
    {
        return new[] { value.x, value.y, value.z };
    }

    private DurationPlan BuildDurationPlan(GameObject root, string captureCategory)
    {
        var config = requestManifest.sampling ?? new SamplingConfig();
        var plan = new DurationPlan();
        var duration = 0f;
        foreach (var system in root.GetComponentsInChildren<ParticleSystem>(true))
        {
            var main = system.main;
            var delay = CurveMaximum(main.startDelay);
            var lifetime = CurveMaximum(main.startLifetime);
            var particleDuration = main.loop ? delay + main.duration : delay + main.duration + lifetime;
            duration = Mathf.Max(duration, particleDuration);
            plan.Looping |= main.loop;
            plan.Basis.Add($"particle:{system.name}:delay={delay:0.###},duration={main.duration:0.###},lifetime={lifetime:0.###},loop={main.loop}");
        }

        foreach (var animator in root.GetComponentsInChildren<Animator>(true))
        {
            var controller = animator.runtimeAnimatorController;
            if (controller == null)
                continue;
            foreach (var clip in controller.animationClips)
            {
                duration = Mathf.Max(duration, clip.length);
                plan.Looping |= clip.isLooping;
                plan.Basis.Add($"animator:{clip.name}:length={clip.length:0.###},loop={clip.isLooping}");
            }
        }

        foreach (var animation in root.GetComponentsInChildren<Animation>(true))
        {
            foreach (AnimationState state in animation)
            {
                duration = Mathf.Max(duration, state.length);
                plan.Basis.Add($"animation:{state.name}:length={state.length:0.###}");
            }
        }

        foreach (var director in root.GetComponentsInChildren<PlayableDirector>(true))
        {
            if (!double.IsNaN(director.duration) && !double.IsInfinity(director.duration))
            {
                duration = Mathf.Max(duration, (float)director.duration);
                plan.Basis.Add($"timeline:{director.name}:duration={director.duration:0.###}");
            }
        }

        foreach (var trail in root.GetComponentsInChildren<TrailRenderer>(true))
        {
            duration = Mathf.Max(duration, trail.time);
            plan.Basis.Add($"trail:{trail.name}:time={trail.time:0.###}");
        }

        plan.ComponentDuration = duration;
        plan.SubjectDuration = EstimateSubjectDuration(root, captureCategory);
        if (string.Equals(captureCategory, "slash", StringComparison.OrdinalIgnoreCase)
            && plan.SubjectDuration > 0f
            && plan.SubjectDuration < duration)
        {
            duration = plan.SubjectDuration;
            plan.SubjectDurationOverride = true;
            plan.Basis.Add($"subject_duration_override:subject={plan.SubjectDuration:0.###},component={plan.ComponentDuration:0.###}");
        }

        var customScripts = root.GetComponentsInChildren<MonoBehaviour>(true)
            .Where(value => value != null && value != this)
            .ToArray();
        var controlledScripts = customScripts.OfType<IEffectDemoCaptureTimingProvider>().ToArray();
        foreach (var controlled in controlledScripts)
        {
            duration = Mathf.Max(duration, controlled.CaptureDurationSeconds);
            plan.Basis.Add($"controlled_script:{controlled.GetType().FullName}:duration={controlled.CaptureDurationSeconds:0.###}");
        }
        var unknownScripts = customScripts
            .Where(value => !(value is IEffectDemoCaptureTimingProvider))
            .Select(value => value.GetType().FullName)
            .Distinct()
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
        plan.HasCustomScriptTiming = unknownScripts.Length > 0;
        if (plan.HasCustomScriptTiming)
            plan.Basis.Add($"custom_scripts_unbounded:{string.Join(",", unknownScripts)}");

        plan.UnclampedDuration = duration > 0f ? duration : 1f;
        duration = Mathf.Clamp(plan.UnclampedDuration, config.min_interval_seconds, config.max_duration_seconds);
        plan.DurationClamped = plan.UnclampedDuration > config.max_duration_seconds + 0.0001f;
        if (plan.DurationClamped)
            plan.Basis.Add($"duration_clamped:unclamped={plan.UnclampedDuration:0.###},maximum={config.max_duration_seconds:0.###}");
        var targetIntervals = Mathf.Max(1, config.target_intervals);
        if (plan.SubjectDurationOverride)
            targetIntervals = Mathf.Max(targetIntervals, Mathf.Max(1, config.short_effect_target_intervals));
        var rawInterval = Mathf.Clamp(duration / targetIntervals, config.min_interval_seconds, config.max_interval_seconds);
        var steps = Mathf.Max(1, Mathf.CeilToInt(duration / rawInterval));
        plan.Duration = duration;
        plan.Interval = duration / steps;
        if (config.include_zero)
            plan.Times.Add(0f);
        for (var index = 1; index <= steps; index++)
            plan.Times.Add((float)Math.Round(index * plan.Interval, 4));
        return plan;
    }

    private static float EstimateSubjectDuration(GameObject root, string captureCategory)
    {
        var duration = 0f;
        foreach (var system in root.GetComponentsInChildren<ParticleSystem>(true))
        {
            var renderer = system.GetComponent<ParticleSystemRenderer>();
            if (!IsSubjectRenderer(renderer, captureCategory))
                continue;
            var main = system.main;
            var delay = CurveMaximum(main.startDelay);
            var lifetime = CurveMaximum(main.startLifetime);
            var emission = system.emission;
            var continuousEmission = emission.enabled
                && (CurveMaximum(emission.rateOverTime) > 0.0001f || CurveMaximum(emission.rateOverDistance) > 0.0001f);
            var particleDuration = main.loop && !continuousEmission
                ? delay + lifetime
                : delay + main.duration + (main.loop ? 0f : lifetime);
            duration = Mathf.Max(duration, particleDuration);
        }
        return duration;
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

    private static void ResetAndPlay(GameObject root)
    {
        foreach (var system in root.GetComponentsInChildren<ParticleSystem>(true))
        {
            system.Stop(false, ParticleSystemStopBehavior.StopEmittingAndClear);
            system.Clear(false);
            system.Play(false);
        }
        foreach (var animator in root.GetComponentsInChildren<Animator>(true))
        {
            animator.Rebind();
            animator.Update(0f);
        }
        foreach (var animation in root.GetComponentsInChildren<Animation>(true))
        {
            animation.Rewind();
            animation.Play();
        }
        foreach (var director in root.GetComponentsInChildren<PlayableDirector>(true))
        {
            director.time = 0;
            director.Evaluate();
            director.Play();
        }
    }

    private static void AccumulateBounds(GameObject root, ref bool found, ref Bounds bounds)
    {
        foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
        {
            if (!renderer.enabled || !renderer.gameObject.activeInHierarchy)
                continue;
            var candidate = renderer.bounds;
            if (candidate.size.sqrMagnitude < 0.000001f || float.IsNaN(candidate.center.x) || float.IsInfinity(candidate.center.x))
                continue;
            if (!found)
            {
                bounds = candidate;
                found = true;
            }
            else
            {
                bounds.Encapsulate(candidate);
            }
        }
    }

    private static void AccumulateSubjectBounds(GameObject root, string captureCategory, ref bool found, ref Bounds bounds)
    {
        foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
        {
            if (!IsSubjectRenderer(renderer, captureCategory)
                || !renderer.enabled
                || !renderer.gameObject.activeInHierarchy)
                continue;
            var candidate = renderer.bounds;
            if (candidate.size.sqrMagnitude < 0.000001f || float.IsNaN(candidate.center.x) || float.IsInfinity(candidate.center.x))
                continue;
            if (!found)
            {
                bounds = candidate;
                found = true;
            }
            else
            {
                bounds.Encapsulate(candidate);
            }
        }
    }

    private static bool IsSubjectRenderer(Renderer renderer, string captureCategory)
    {
        var particleRenderer = renderer as ParticleSystemRenderer;
        if (particleRenderer != null && particleRenderer.renderMode == ParticleSystemRenderMode.Mesh && particleRenderer.mesh != null)
            return true;
        if (!string.Equals(captureCategory, "slash", StringComparison.OrdinalIgnoreCase))
            return false;
        var name = renderer.gameObject.name.ToLowerInvariant();
        return name.Contains("slash") || name.Contains("sword") || name.Contains("blade") || name.Contains("core");
    }

    private static void AddCameraView(List<CameraView> views, string name, Vector3 forward, Vector3 up)
    {
        if (forward.sqrMagnitude < 0.000001f)
            return;
        forward.Normalize();
        if (views.Any(value => Vector3.Dot(value.Forward, forward) > 0.999f))
            return;
        var projectedUp = Vector3.ProjectOnPlane(up, forward);
        if (projectedUp.sqrMagnitude < 0.000001f)
            projectedUp = Vector3.ProjectOnPlane(Vector3.up, forward);
        if (projectedUp.sqrMagnitude < 0.000001f)
            projectedUp = Vector3.ProjectOnPlane(Vector3.right, forward);
        views.Add(new CameraView { Name = name, Forward = forward, Up = projectedUp.normalized });
    }

    private static Vector3 VectorFromArray(float[] value, Vector3 fallback)
    {
        return value != null && value.Length >= 3
            ? new Vector3(value[0], value[1], value[2]).normalized
            : fallback;
    }

    private static bool IsOrthographicProfile(string captureCategory)
    {
        return string.Equals(captureCategory, "slash", StringComparison.OrdinalIgnoreCase);
    }

    private void ConfigureCaptureRig()
    {
        contextRoot = new GameObject("VFXCaptureStandardContext");
        var cameraObject = new GameObject(requestManifest.camera ?? "RuntimeCaptureCamera");
        cameraObject.transform.SetParent(contextRoot.transform, false);
        cameraObject.tag = "MainCamera";
        captureCamera = cameraObject.AddComponent<Camera>();
        captureCamera.clearFlags = CameraClearFlags.SolidColor;
        captureCamera.backgroundColor = new Color(0.015f, 0.02f, 0.035f, 1f);
        var requestedBackground = requestManifest.background_color_rgba;
        if (requestedBackground != null && requestedBackground.Length > 0)
        {
            if (requestedBackground.Length != 4 || requestedBackground.Any(value => float.IsNaN(value) || float.IsInfinity(value) || value < 0f || value > 1f))
                throw new InvalidOperationException("background_color_rgba must contain four finite values in [0, 1].");
            captureCamera.backgroundColor = new Color(requestedBackground[0], requestedBackground[1], requestedBackground[2], requestedBackground[3]);
        }
        captureCamera.fieldOfView = 42f;
        captureCamera.nearClipPlane = 0.01f;
        captureCamera.farClipPlane = 1000f;
        captureCamera.allowHDR = false;
        captureCamera.allowMSAA = false;
        captureCamera.useOcclusionCulling = false;
        captureCamera.aspect = (float)requestManifest.width / requestManifest.height;
        renderTarget = new RenderTexture(requestManifest.width, requestManifest.height, 24, RenderTextureFormat.ARGB32);
        renderTarget.Create();
        cameraEvaluationTarget = new RenderTexture(160, 160, 24, RenderTextureFormat.ARGB32);
        cameraEvaluationTarget.Create();
        captureCamera.targetTexture = renderTarget;

        var lightObject = new GameObject("RuntimeCaptureLight");
        lightObject.transform.SetParent(contextRoot.transform, false);
        captureLight = lightObject.AddComponent<Light>();
        captureLight.type = LightType.Directional;
        captureLight.intensity = 1.5f;
        captureLight.color = Color.white;
        captureLight.transform.rotation = Quaternion.Euler(40f, -35f, 0f);

        var eventSystemObject = new GameObject("VFXCaptureEventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
        eventSystemObject.transform.SetParent(contextRoot.transform, false);
        var ground = new GameObject("VFXCaptureGroundAnchor", typeof(BoxCollider));
        ground.transform.SetParent(contextRoot.transform, false);
        ground.transform.position = new Vector3(0f, -0.05f, 0f);
        ground.GetComponent<BoxCollider>().size = new Vector3(30f, 0.1f, 30f);
        var target = new GameObject("VFXCaptureTarget", typeof(SphereCollider));
        target.transform.SetParent(contextRoot.transform, false);
        target.transform.position = new Vector3(2f, 1f, 0f);
        target.GetComponent<SphereCollider>().radius = 0.5f;
        var character = new GameObject("VFXCaptureCharacterAnchor");
        character.transform.SetParent(contextRoot.transform, false);
    }

    private void FrameCamera(Bounds bounds, CameraView view)
    {
        var rotation = Quaternion.LookRotation(view.Forward, view.Up);
        var right = rotation * Vector3.right;
        var up = rotation * Vector3.up;
        var forward = rotation * Vector3.forward;
        var extents = bounds.extents;
        var halfWidth = Mathf.Abs(right.x) * extents.x + Mathf.Abs(right.y) * extents.y + Mathf.Abs(right.z) * extents.z;
        var halfHeight = Mathf.Abs(up.x) * extents.x + Mathf.Abs(up.y) * extents.y + Mathf.Abs(up.z) * extents.z;
        var halfDepth = Mathf.Abs(forward.x) * extents.x + Mathf.Abs(forward.y) * extents.y + Mathf.Abs(forward.z) * extents.z;
        var fittedHalfHeight = Mathf.Max(0.125f, Mathf.Max(halfHeight, halfWidth / Mathf.Max(0.1f, captureCamera.aspect)));
        float distance;
        if (captureCamera.orthographic)
        {
            captureCamera.orthographicSize = fittedHalfHeight * 2f * 1.15f;
            distance = Mathf.Max(0.5f, halfDepth + 1f);
        }
        else
        {
            distance = Mathf.Max(0.35f, fittedHalfHeight / Mathf.Tan(captureCamera.fieldOfView * 0.5f * Mathf.Deg2Rad) * 1.2f + halfDepth);
        }
        captureCamera.transform.position = bounds.center - view.Forward * distance;
        captureCamera.transform.rotation = rotation;
        captureLight.transform.position = captureCamera.transform.position + Vector3.up * 2f;
    }

    private FramePixelMetrics WriteCameraPng(string destination)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(destination));
        return RenderPixelMetrics(renderTarget, true, destination);
    }

    private FramePixelMetrics RenderPixelMetrics(RenderTexture target, bool writePng, string destination)
    {
        var previousTarget = captureCamera.targetTexture;
        var previousActive = RenderTexture.active;
        captureCamera.targetTexture = target;
        captureCamera.Render();
        RenderTexture.active = target;
        var texture = new Texture2D(target.width, target.height, TextureFormat.RGBA32, false);
        try
        {
            texture.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0);
            texture.Apply(false, false);
            var metrics = AnalyzePixels(texture.GetPixels32(), target.width, target.height);
            if (writePng)
                File.WriteAllBytes(destination, texture.EncodeToPNG());
            return metrics;
        }
        finally
        {
            RenderTexture.active = previousActive;
            captureCamera.targetTexture = previousTarget;
            Destroy(texture);
        }
    }

    private FramePixelMetrics AnalyzePixels(Color32[] pixels, int width, int height)
    {
        var background = (Color32)captureCamera.backgroundColor;
        var visible = 0;
        var borderVisible = 0;
        var errorMagenta = 0;
        double xSum = 0;
        double ySum = 0;
        const int border = 3;
        for (var y = 0; y < height; y++)
        {
            for (var x = 0; x < width; x++)
            {
                var color = pixels[y * width + x];
                if (color.r >= 250 && color.g <= 8 && color.b >= 250)
                    errorMagenta++;
                var difference = Mathf.Max(Mathf.Abs(color.r - background.r), Mathf.Abs(color.g - background.g), Mathf.Abs(color.b - background.b));
                if (difference <= 8)
                    continue;
                visible++;
                xSum += x;
                ySum += y;
                if (x < border || x >= width - border || y < border || y >= height - border)
                    borderVisible++;
            }
        }
        var total = Mathf.Max(1, width * height);
        var visibleRatio = (float)visible / total;
        var errorMagentaRatio = (float)errorMagenta / total;
        var errorMagentaVisibleRatio = visible == 0 ? 0f : (float)errorMagenta / visible;
        var borderRatio = visible == 0 ? 0f : (float)borderVisible / visible;
        var centerOffset = 1f;
        if (visible > 0)
        {
            var centerX = xSum / visible;
            var centerY = ySum / visible;
            var dx = (centerX - (width - 1) * 0.5) / Mathf.Max(1f, width * 0.5f);
            var dy = (centerY - (height - 1) * 0.5) / Mathf.Max(1f, height * 0.5f);
            centerOffset = Mathf.Clamp01((float)Math.Sqrt(dx * dx + dy * dy));
        }
        return new FramePixelMetrics
        {
            visible_area_ratio = visibleRatio,
            border_touch_ratio = borderRatio,
            center_offset_normalized = centerOffset,
            unity_error_magenta_ratio = errorMagentaRatio,
            unity_error_magenta_pixel_count = errorMagenta,
            unity_error_magenta_visible_ratio = errorMagentaVisibleRatio,
            material_render_error = errorMagenta >= 64 && errorMagentaRatio >= 0.001f && errorMagentaVisibleRatio >= 0.5f,
            near_blank = visibleRatio < 0.001f,
            cropped = borderRatio > 0.02f,
        };
    }

    private void WriteFailure(RequestItem request, string error)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.capture_manifest_path))
            return;
        var plan = new DurationPlan { Duration = 0f, Interval = 0f };
        var recorder = new EffectDemoMaterialStateRecorder();
        var timeline = recorder.CreateTimeline(request);
        recorder.Complete(timeline, error);
        WriteTimeline(request, timeline);
        WriteManifest(request, plan, new List<CaptureFrame>(), 0, timeline, null, error);
        Debug.LogWarning($"Runtime VFX capture failed for {request.candidate_id}: {error}");
    }

    private void WriteManifest(RequestItem request, DurationPlan plan, List<CaptureFrame> frames, int particleSystemCount, EffectDemoMaterialStateRecorder.Timeline timeline, CandidateRuntimeEvidence evidence, string error)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(request.capture_manifest_path));
        var validFrameCount = frames.FindAll(frame => frame.valid).Count;
        var technicalFrameEligible = string.IsNullOrWhiteSpace(error) && frames.Count > 0 && validFrameCount == frames.Count;
        var hasVisibleFrame = frames.Any(frame => frame.pixel_metrics != null && !frame.pixel_metrics.near_blank);
        var allFramesUncropped = frames.All(frame => frame.pixel_metrics == null || !frame.pixel_metrics.cropped);
        var materialRenderErrorFrameCount = frames.Count(frame => frame.pixel_metrics != null && frame.pixel_metrics.material_render_error);
        var hasMaterialRenderError = materialRenderErrorFrameCount > 0;
        var contextReady = evidence?.Context?.status == "standard_context_ready";
        var hasUnenumeratedPropertyBlockValues = timeline?.summary?.has_unenumerated_property_block_values ?? false;
        var pipelineInstance = UnityEngine.Rendering.RenderPipelineManager.currentPipeline;
        var pipelineInstanceType = pipelineInstance?.GetType().FullName ?? "no_active_srp";
        var expectedPipelineType = string.IsNullOrWhiteSpace(requestManifest?.expected_render_pipeline_type)
            ? "UnityEngine.Rendering.Universal.UniversalRenderPipeline"
            : requestManifest.expected_render_pipeline_type;
        var pipelineVerified = pipelineInstance != null && string.Equals(pipelineInstanceType, expectedPipelineType, StringComparison.Ordinal);
        var imageSequenceEligible = pipelineVerified && technicalFrameEligible && hasVisibleFrame && allFramesUncropped && contextReady && !hasMaterialRenderError;
        var fullVisualEligible = imageSequenceEligible
            && !(evidence?.Context?.unknown_custom_script_count > 0)
            && !hasUnenumeratedPropertyBlockValues
            && string.Equals(timeline?.summary?.global_shader_state_status, "instrumented", StringComparison.Ordinal);
        var limitations = new List<string>();
        if (evidence?.Context?.limitations != null)
            limitations.AddRange(evidence.Context.limitations);
        if (!pipelineVerified)
            limitations.Add($"Runtime render pipeline {pipelineInstanceType} does not match expected {expectedPipelineType}; diagnostic frames are not training evidence.");
        if (plan.DurationClamped)
            limitations.Add($"Duration was clamped from {plan.UnclampedDuration:0.###}s to {plan.Duration:0.###}s.");
        if (!hasVisibleFrame)
            limitations.Add("No captured frame passed the visible-pixel threshold.");
        if (!allFramesUncropped)
            limitations.Add("At least one frame touches the capture border and may be cropped.");
        if (hasMaterialRenderError)
            limitations.Add("Unity error-magenta pixels indicate a missing, incompatible, or failed runtime material Shader.");
        if (hasUnenumeratedPropertyBlockValues)
            limitations.Add("A non-empty MaterialPropertyBlock contained property IDs that could not be enumerated.");
        if (!string.Equals(timeline?.summary?.global_shader_state_status, "instrumented", StringComparison.Ordinal))
            limitations.Add("Shader global properties are not instrumented; full dynamic-material fidelity is unavailable.");
        var visualEvidenceStatus = !technicalFrameEligible ? "technical_failure"
            : !pipelineVerified ? "render_pipeline_mismatch"
            : hasMaterialRenderError ? "material_render_error"
            : !hasVisibleFrame ? "near_blank"
            : !contextReady ? "incomplete_context"
            : !allFramesUncropped ? "cropped"
            : fullVisualEligible ? "full_visual_evidence"
            : "image_sequence_partial_material_fidelity";
        var manifest = new CaptureManifest
        {
            created_at = DateTime.UtcNow.ToString("o"),
            unity_version = Application.unityVersion,
            active_render_pipeline_type = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline?.GetType().FullName ?? "no_active_srp",
            configured_render_pipeline_type = UnityEngine.Rendering.GraphicsSettings.renderPipelineAsset?.GetType().FullName ?? "no_loaded_default_srp_asset",
            render_pipeline_instance_type = pipelineInstanceType,
            expected_render_pipeline_type = expectedPipelineType,
            render_pipeline_verified = pipelineVerified,
            graphics_device_type = SystemInfo.graphicsDeviceType.ToString(),
            color_space = QualitySettings.activeColorSpace.ToString(),
            background_color_rgba = captureCamera == null ? requestManifest?.background_color_rgba
                : new[] { captureCamera.backgroundColor.r, captureCamera.backgroundColor.g, captureCamera.backgroundColor.b, captureCamera.backgroundColor.a },
            particle_seed_key = string.IsNullOrWhiteSpace(request.random_seed_key) ? request.candidate_id : request.random_seed_key,
            capture_category = request.capture_category,
            capture_root = request.capture_dir,
            scene = requestManifest.scene,
            effect = request.prefab_path,
            camera = requestManifest.camera,
            resolution = new[] { requestManifest.width, requestManifest.height },
            editor_status = "play_mode_runtime",
            capture_mode = "play_mode_runtime",
            sampling_mode = "adaptive_runtime",
            play_requested = true,
            looping = plan.Looping,
            unclamped_duration_seconds = plan.UnclampedDuration,
            component_duration_seconds = plan.ComponentDuration,
            subject_duration_seconds = plan.SubjectDuration,
            subject_duration_override = plan.SubjectDurationOverride,
            duration_clamped = plan.DurationClamped,
            custom_script_timing_unknown = plan.HasCustomScriptTiming,
            duration_seconds = plan.Duration,
            sample_interval_seconds = plan.Interval,
            time_points_seconds = plan.Times.ToArray(),
            sampling_basis = plan.Basis.ToArray(),
            frames = frames.ToArray(),
            valid_frame_count = validFrameCount,
            invalid_frame_count = frames.FindAll(frame => !frame.valid).Count,
            render_error = error,
            particle_system_count = particleSystemCount,
            material_timeline_path = ResolveTimelinePath(request),
            material_timeline_frame_count = timeline?.summary?.frame_count ?? 0,
            material_change_count = timeline?.summary?.delta_count ?? 0,
            material_render_error_frame_count = materialRenderErrorFrameCount,
            has_dynamic_material_state = timeline?.summary?.has_dynamic_material_state ?? false,
            material_capture_sync = "late_update_execution_order_32000",
            has_unenumerated_property_block_values = hasUnenumeratedPropertyBlockValues,
            global_shader_state_status = timeline?.summary?.global_shader_state_status ?? "not_available",
            instance_isolation_mode = "fresh_bounds_probe_then_fresh_camera_probe_then_fresh_capture_instance",
            bounds_probe_instance_id = evidence?.BoundsProbeInstanceId ?? 0,
            camera_probe_instance_id = evidence?.CameraProbeInstanceId ?? 0,
            capture_instance_id = evidence?.CaptureInstanceId ?? 0,
            distinct_instance_ids = evidence != null
                && evidence.BoundsProbeInstanceId != 0
                && evidence.CameraProbeInstanceId != 0
                && evidence.CaptureInstanceId != 0
                && evidence.BoundsProbeInstanceId != evidence.CameraProbeInstanceId
                && evidence.BoundsProbeInstanceId != evidence.CaptureInstanceId
                && evidence.CameraProbeInstanceId != evidence.CaptureInstanceId,
            accumulated_bounds = evidence == null ? null : new BoundsEvidence
            {
                found = evidence.BoundsFound,
                center = Vector(evidence.Bounds.center),
                size = Vector(evidence.Bounds.size),
                sample_count = evidence.BoundsSampleCount,
            },
            subject_bounds = evidence == null ? null : new BoundsEvidence
            {
                found = evidence.SubjectBoundsFound,
                center = Vector(evidence.SubjectBounds.center),
                size = Vector(evidence.SubjectBounds.size),
                sample_count = evidence.SubjectBoundsSampleCount,
            },
            camera_selection = evidence?.CameraSelection,
            context = evidence?.Context,
            particle_random_seeds = evidence?.Seeds ?? Array.Empty<RandomSeedEvidence>(),
            technical_frame_eligible = technicalFrameEligible,
            image_sequence_training_eligible = imageSequenceEligible,
            full_visual_training_eligible = fullVisualEligible,
            visual_evidence_status = visualEvidenceStatus,
            visual_evidence_limitations = limitations.Distinct().ToArray(),
        };
        File.WriteAllText(request.capture_manifest_path, JsonUtility.ToJson(manifest, true) + "\n");
    }

    private static void WriteTimeline(RequestItem request, EffectDemoMaterialStateRecorder.Timeline timeline)
    {
        var path = ResolveTimelinePath(request);
        var parent = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(parent))
            Directory.CreateDirectory(parent);
        File.WriteAllText(path, JsonUtility.ToJson(timeline, true) + "\n");
    }

    private static string ResolveTimelinePath(RequestItem request)
    {
        if (!string.IsNullOrWhiteSpace(request.material_timeline_path))
            return request.material_timeline_path;
        return Path.Combine(Path.GetDirectoryName(request.capture_manifest_path), "material_timeline.json");
    }

    private IEnumerator ExecuteAfterLateUpdate(Action action, double notBeforeSimulationTime = 0d)
    {
        if (pendingLateCapture != null)
            throw new InvalidOperationException("A material capture is already waiting for LateUpdate.");
        lateCaptureCompleted = false;
        lateCaptureException = null;
        pendingLateCaptureNotBeforeSimulationTime = notBeforeSimulationTime;
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
        if (Time.timeAsDouble + 0.000001d < pendingLateCaptureNotBeforeSimulationTime)
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
            Destroy(renderTarget);
        if (cameraEvaluationTarget != null)
            Destroy(cameraEvaluationTarget);
        if (contextRoot != null)
            Destroy(contextRoot);
    }
}
