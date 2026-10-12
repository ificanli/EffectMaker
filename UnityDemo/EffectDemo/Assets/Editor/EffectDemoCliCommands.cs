using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Batch-mode entry points for the Unity 2022 EffectDemo project.
/// These commands are intentionally independent of com.unity.pipeline so the
/// legacy project can be driven by Unity CLI without importing a Unity 6-only package.
/// </summary>
public static class EffectDemoCliCommands
{
    // Keep this entry point independent from the optional live Pipeline assembly.
    private const string RootFolder = "Assets/Art/VFX/CliSamples";
    private const string PrefabPath = RootFolder + "/CliSmokeEffect.prefab";
    private const string MaterialPath = RootFolder + "/CliSmokeEffect.mat";
    private const string SourceRenderRequestsEnvironment = "EFFECTDEMO_SOURCE_RENDER_REQUESTS";
    private const string SourceRenderRequestSchema = "effectdemo_source_render_requests.v1";

    [Serializable]
    private sealed class SourceRenderRequestManifest
    {
        public string schema_version;
        public string run_id;
        public string scene;
        public string camera;
        public int width;
        public int height;
        public float[] time_points_seconds;
        public SourceRenderRequest[] requests;
    }

    [Serializable]
    private sealed class SourceRenderRequest
    {
        public string candidate_id;
        public string prefab_path;
        public string capture_dir;
        public string capture_manifest_path;
    }

    [Serializable]
    private sealed class SourceCaptureManifest
    {
        public string schema = "unity-capture-manifest.v1";
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
        public SourceCaptureFrame[] frames;
        public int valid_frame_count;
        public int invalid_frame_count;
        public string render_error;
        public int particle_system_count;
    }

    [Serializable]
    private sealed class SourceCaptureFrame
    {
        public float requested_time_seconds;
        public float capture_time_seconds;
        public string path;
        public bool valid;
        public string error;
        public int file_size;
    }

    public static void CreateCliSmokeEffect()
    {
        EnsureFolder(RootFolder);

        var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit")
            ?? Shader.Find("Particles/Standard Unlit")
            ?? Shader.Find("Unlit/Color");
        if (shader == null)
            throw new System.InvalidOperationException("No compatible particle shader was found.");

        var material = AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
        if (material == null)
        {
            material = new Material(shader) { name = "CliSmokeEffect" };
            AssetDatabase.CreateAsset(material, MaterialPath);
        }
        material.color = new Color(0.15f, 0.65f, 1f, 0.85f);
        EditorUtility.SetDirty(material);

        var existing = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
        if (existing != null)
            AssetDatabase.DeleteAsset(PrefabPath);

        var root = new GameObject("CliSmokeEffect");
        var particleSystem = root.AddComponent<ParticleSystem>();
        var main = particleSystem.main;
        main.loop = true;
        main.duration = 2f;
        main.startLifetime = 1.2f;
        main.startSpeed = 0.35f;
        main.startSize = 0.28f;
        main.startColor = new Color(0.15f, 0.65f, 1f, 0.85f);
        main.maxParticles = 64;

        var emission = particleSystem.emission;
        emission.rateOverTime = 18f;

        var shape = particleSystem.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.15f;

        var renderer = root.GetComponent<ParticleSystemRenderer>();
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
        renderer.material = material;

        PrefabUtility.SaveAsPrefabAsset(root, PrefabPath);
        UnityEngine.Object.DestroyImmediate(root);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"EffectDemo CLI smoke effect created: {PrefabPath}");
    }

    public static void RemoveCliSmokeEffect()
    {
        if (AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(PrefabPath) != null)
            AssetDatabase.DeleteAsset(PrefabPath);
        if (AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(MaterialPath) != null)
            AssetDatabase.DeleteAsset(MaterialPath);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log("EffectDemo CLI smoke effect removed.");
    }

    /// <summary>
    /// Renders source-ingest candidates described by a JSON file supplied through
    /// EFFECTDEMO_SOURCE_RENDER_REQUESTS. The request is generated outside Unity
    /// so this command never needs to alter the imported Prefab or its assets.
    /// </summary>
    public static void RenderSourceIngestFromEnvironment()
    {
        var requestPath = Environment.GetEnvironmentVariable(SourceRenderRequestsEnvironment);
        if (string.IsNullOrWhiteSpace(requestPath) || !File.Exists(requestPath))
            throw new InvalidOperationException($"Set {SourceRenderRequestsEnvironment} to an existing render_requests.json file.");

        var request = JsonUtility.FromJson<SourceRenderRequestManifest>(File.ReadAllText(requestPath));
        if (request == null || request.schema_version != SourceRenderRequestSchema)
            throw new InvalidOperationException($"Unsupported source render request schema in {requestPath}.");
        if (request.width <= 0 || request.height <= 0)
            throw new InvalidOperationException("Source render request resolution must be positive.");
        if (request.requests == null || request.requests.Length == 0)
            throw new InvalidOperationException("Source render request does not contain any candidates.");

        var timePoints = request.time_points_seconds == null || request.time_points_seconds.Length == 0
            ? new[] { 0f }
            : request.time_points_seconds;
        var completed = 0;
        foreach (var item in request.requests)
        {
            try
            {
                RenderSourcePrefab(item, request, timePoints);
                completed++;
            }
            catch (Exception exception)
            {
                WriteFailedCaptureManifest(item, request, timePoints, exception.Message);
                Debug.LogWarning($"Source VFX render failed for {item.candidate_id}: {exception.Message}");
            }
        }

        Debug.Log($"EffectDemo source VFX render completed: {completed}/{request.requests.Length} candidates. Run: {request.run_id}");
    }

    private static void RenderSourcePrefab(SourceRenderRequest item, SourceRenderRequestManifest request, float[] timePoints)
    {
        if (item == null || string.IsNullOrWhiteSpace(item.prefab_path) || string.IsNullOrWhiteSpace(item.capture_dir) || string.IsNullOrWhiteSpace(item.capture_manifest_path))
            throw new InvalidOperationException("Source render candidate is missing prefab_path, capture_dir, or capture_manifest_path.");
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(item.prefab_path);
        if (prefab == null)
            throw new FileNotFoundException($"Prefab could not be loaded: {item.prefab_path}");

        Directory.CreateDirectory(item.capture_dir);
        var instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
        if (instance == null)
            throw new InvalidOperationException($"Prefab could not be instantiated: {item.prefab_path}");
        var cameraRoot = new GameObject(request.camera);
        var reviewCamera = cameraRoot.AddComponent<Camera>();
        var lightRoot = new GameObject("SourceIngestReviewLight");
        var reviewLight = lightRoot.AddComponent<Light>();
        var renderTarget = new RenderTexture(request.width, request.height, 24, RenderTextureFormat.ARGB32);

        try
        {
            ConfigureReviewCamera(reviewCamera, request.width, request.height);
            ConfigureReviewLight(reviewLight);
            var particleSystems = instance.GetComponentsInChildren<ParticleSystem>(true);
            SimulateParticleSystems(particleSystems, MaxTimePoint(timePoints));
            FrameReviewCamera(reviewCamera, reviewLight, CalculateBounds(instance), request.width, request.height);
            reviewCamera.targetTexture = renderTarget;
            var frames = new List<SourceCaptureFrame>();
            foreach (var timePoint in timePoints)
            {
                SimulateParticleSystems(particleSystems, timePoint);
                var frameName = $"frame_{timePoint:0.000}".Replace('.', '_') + ".png";
                var framePath = Path.Combine(item.capture_dir, frameName);
                WriteCameraPng(reviewCamera, renderTarget, framePath, request.width, request.height);
                var info = new FileInfo(framePath);
                frames.Add(new SourceCaptureFrame
                {
                    requested_time_seconds = timePoint,
                    capture_time_seconds = timePoint,
                    path = frameName,
                    valid = info.Exists && info.Length > 0,
                    error = info.Exists && info.Length > 0 ? null : "capture file is empty",
                    file_size = info.Exists ? (int)Math.Min(info.Length, int.MaxValue) : 0,
                });
            }
            WriteCaptureManifest(item, request, frames, particleSystems.Length, null);
        }
        finally
        {
            reviewCamera.targetTexture = null;
            RenderTexture.active = null;
            UnityEngine.Object.DestroyImmediate(renderTarget);
            UnityEngine.Object.DestroyImmediate(lightRoot);
            UnityEngine.Object.DestroyImmediate(cameraRoot);
            UnityEngine.Object.DestroyImmediate(instance);
        }
    }

    private static void WriteFailedCaptureManifest(SourceRenderRequest item, SourceRenderRequestManifest request, float[] timePoints, string error)
    {
        if (item == null || string.IsNullOrWhiteSpace(item.capture_manifest_path))
            return;
        var frames = new List<SourceCaptureFrame>();
        foreach (var timePoint in timePoints)
        {
            frames.Add(new SourceCaptureFrame
            {
                requested_time_seconds = timePoint,
                capture_time_seconds = timePoint,
                path = null,
                valid = false,
                error = error,
                file_size = 0,
            });
        }
        WriteCaptureManifest(item, request, frames, 0, error);
    }

    private static void WriteCaptureManifest(SourceRenderRequest item, SourceRenderRequestManifest request, List<SourceCaptureFrame> frames, int particleSystemCount, string renderError)
    {
        var manifestDirectory = Path.GetDirectoryName(item.capture_manifest_path);
        if (string.IsNullOrWhiteSpace(manifestDirectory))
            throw new InvalidOperationException($"Capture manifest path must include a directory: {item.capture_manifest_path}");
        Directory.CreateDirectory(manifestDirectory);
        var manifest = new SourceCaptureManifest
        {
            created_at = DateTime.UtcNow.ToString("o"),
            capture_root = string.IsNullOrWhiteSpace(item.capture_dir) ? manifestDirectory : item.capture_dir,
            scene = request.scene,
            effect = item.prefab_path,
            camera = request.camera,
            resolution = new[] { request.width, request.height },
            editor_status = "batchmode_camera_render",
            capture_mode = "editor_particle_simulation",
            sampling_mode = "fixed_editor_simulation",
            play_requested = false,
            frames = frames.ToArray(),
            valid_frame_count = frames.FindAll(frame => frame.valid).Count,
            invalid_frame_count = frames.FindAll(frame => !frame.valid).Count,
            render_error = renderError,
            particle_system_count = particleSystemCount,
        };
        File.WriteAllText(item.capture_manifest_path, JsonUtility.ToJson(manifest, true) + "\n");
    }

    private static void ConfigureReviewCamera(Camera reviewCamera, int width, int height)
    {
        reviewCamera.clearFlags = CameraClearFlags.SolidColor;
        reviewCamera.backgroundColor = new Color(0.015f, 0.02f, 0.035f, 1f);
        reviewCamera.fieldOfView = 42f;
        reviewCamera.nearClipPlane = 0.01f;
        reviewCamera.farClipPlane = 1000f;
        reviewCamera.allowHDR = false;
        reviewCamera.allowMSAA = false;
        reviewCamera.useOcclusionCulling = false;
        reviewCamera.aspect = (float)width / height;
    }

    private static void ConfigureReviewLight(Light reviewLight)
    {
        reviewLight.type = LightType.Directional;
        reviewLight.intensity = 1.5f;
        reviewLight.color = Color.white;
        reviewLight.transform.rotation = Quaternion.Euler(40f, -35f, 0f);
    }

    private static void SimulateParticleSystems(ParticleSystem[] particleSystems, float timePoint)
    {
        foreach (var particleSystem in particleSystems)
            particleSystem.Clear(false);
        foreach (var particleSystem in particleSystems)
            particleSystem.Simulate(timePoint, false, true, true);
    }

    private static float MaxTimePoint(IEnumerable<float> timePoints)
    {
        var maximum = 0f;
        foreach (var timePoint in timePoints)
            maximum = Mathf.Max(maximum, timePoint);
        return maximum;
    }

    private static Bounds CalculateBounds(GameObject instance)
    {
        var renderers = instance.GetComponentsInChildren<Renderer>(true);
        var found = false;
        var bounds = new Bounds(instance.transform.position, Vector3.one);
        foreach (var renderer in renderers)
        {
            if (!renderer.enabled || !renderer.gameObject.activeInHierarchy || renderer.bounds.size.sqrMagnitude < 0.000001f)
                continue;
            if (!found)
            {
                bounds = renderer.bounds;
                found = true;
            }
            else
            {
                bounds.Encapsulate(renderer.bounds);
            }
        }
        return found ? bounds : new Bounds(instance.transform.position, Vector3.one * 2f);
    }

    private static void FrameReviewCamera(Camera reviewCamera, Light reviewLight, Bounds bounds, int width, int height)
    {
        var horizontal = Mathf.Max(bounds.size.x, 0.25f);
        var vertical = Mathf.Max(bounds.size.y, 0.25f);
        var groundOriented = bounds.size.y < Mathf.Max(bounds.size.x, bounds.size.z) * 0.2f;
        var forward = groundOriented ? Vector3.down : Vector3.forward;
        var up = groundOriented ? Vector3.forward : Vector3.up;
        if (groundOriented)
        {
            horizontal = Mathf.Max(bounds.size.x, 0.25f);
            vertical = Mathf.Max(bounds.size.z, 0.25f);
        }
        var aspect = (float)width / height;
        var radius = Mathf.Max(horizontal / aspect, vertical) * 0.7f;
        var distance = Mathf.Max(2f, radius / Mathf.Tan(reviewCamera.fieldOfView * 0.5f * Mathf.Deg2Rad) * 1.25f + bounds.extents.z);
        reviewCamera.transform.position = bounds.center - forward * distance;
        reviewCamera.transform.rotation = Quaternion.LookRotation(forward, up);
        reviewLight.transform.position = reviewCamera.transform.position + Vector3.up * 2f;
    }

    private static void WriteCameraPng(Camera reviewCamera, RenderTexture renderTarget, string destination, int width, int height)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(destination) ?? throw new InvalidOperationException("Frame path must include a directory."));
        reviewCamera.Render();
        var previous = RenderTexture.active;
        RenderTexture.active = renderTarget;
        var texture = new Texture2D(width, height, TextureFormat.RGBA32, false);
        try
        {
            texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            texture.Apply(false, false);
            File.WriteAllBytes(destination, texture.EncodeToPNG());
        }
        finally
        {
            RenderTexture.active = previous;
            UnityEngine.Object.DestroyImmediate(texture);
        }
    }

    private static void EnsureFolder(string assetFolder)
    {
        var absolute = Path.Combine(Directory.GetParent(Application.dataPath).FullName, assetFolder);
        if (!Directory.Exists(absolute))
            Directory.CreateDirectory(absolute);
        AssetDatabase.Refresh();
    }
}
