using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace VfxPrefabWeb.Editor
{
    public static class VfxWebPlayerBuilder
    {
        private const string Root = "Assets/Art/VFX/WebPrefabPlayer";
        private const string GeneratedRoot = Root + "/Generated";
        private const string GeneratedPrefabRoot = GeneratedRoot + "/Prefabs";
        private const string CatalogPath = GeneratedRoot + "/VfxWebCatalog.asset";
        private const string ScenePath = Root + "/Scenes/VfxWebPlayer.unity";
        private const string GroundMaterialPath = GeneratedRoot + "/M_VfxWebGround.mat";
        private const string DefaultBuildPath = "Builds/WebGL/VfxTrainingPlayer2022";
        private const int DefaultPreviewLimit = 5;

        private static readonly string[] PrefabSearchRoots =
        {
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001",
        };

        [Serializable]
        private sealed class BuildManifest
        {
            public string createdAt;
            public string unityVersion;
            public string outputPath;
            public int prefabCount;
            public string[] prefabPaths;
            public string trainingReviewBundlePath;
            public string trainingReviewBundleStatus;
            public string truthCaptureMode;
            public int trainingLinkedPrefabCount;
        }

        [Serializable]
        private sealed class TrainingReviewBundle
        {
            public string schemaVersion;
            public string runId;
            public string sourceUnityProject;
            public string truthCaptureMode;
            public TrainingReviewEntry[] entries;
            [NonSerialized] public string sourcePath;
        }

        [Serializable]
        private sealed class TrainingReviewEntry
        {
            public string webPrefabPath;
            public string sourcePrefabPath;
            public string runId;
            public string candidateId;
            public string trainingCaseId;
            public string effectFamily;
            public string materialTimelinePath;
            public string materialTimelineStatus;
            public int materialChangeCount;
            public float[] materialKeyTimes;
            public string sourceScriptFidelity;
            public string specPath;
            public string renderManifestPath;
            public bool hasSeed;
            public int seed;
            public string generator;
            public string generatorVersion;
        }

        [MenuItem("VFX/Web Prefab Player/Prepare Assets")]
        public static void PrepareAssetsFromMenu()
        {
            PrepareAssets(LoadTrainingReviewBundle());
            Debug.Log("VFX Web Prefab Player assets are ready.");
        }

        [MenuItem("VFX/Web Prefab Player/Build WebGL")]
        public static void BuildFromMenu()
        {
            Build(DefaultBuildPath);
        }

        public static void BuildFromCommandLine()
        {
            var outputPath = ReadCommandLineValue("-buildOutput");
            Build(string.IsNullOrWhiteSpace(outputPath) ? DefaultBuildPath : outputPath);
        }

        private static void Build(string outputPath)
        {
            var trainingBundle = LoadTrainingReviewBundle();
            var catalog = PrepareAssets(trainingBundle);
            var projectRoot = Directory.GetParent(Application.dataPath).FullName;
            var absoluteOutput = Path.GetFullPath(Path.IsPathRooted(outputPath)
                ? outputPath
                : Path.Combine(projectRoot, outputPath));
            Directory.CreateDirectory(absoluteOutput);

            var originalTemplate = PlayerSettings.WebGL.template;
            var originalCompression = PlayerSettings.WebGL.compressionFormat;
            var originalFallback = PlayerSettings.WebGL.decompressionFallback;

            BuildReport report;
            try
            {
                PlayerSettings.WebGL.template = "PROJECT:VfxPrefabPlayer";
                PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
                PlayerSettings.WebGL.decompressionFallback = false;

                report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = new[] { ScenePath },
                    locationPathName = absoluteOutput,
                    target = BuildTarget.WebGL,
                    options = BuildOptions.None,
                });
            }
            finally
            {
                PlayerSettings.WebGL.template = originalTemplate;
                PlayerSettings.WebGL.compressionFormat = originalCompression;
                PlayerSettings.WebGL.decompressionFallback = originalFallback;
            }

            if (report.summary.result != BuildResult.Succeeded)
                throw new BuildFailedException("VFX Web Prefab Player build failed: " + report.summary.result);

            var manifest = new BuildManifest
            {
                createdAt = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture),
                unityVersion = Application.unityVersion,
                outputPath = absoluteOutput.Replace('\\', '/'),
                prefabCount = catalog.Entries.Count,
                prefabPaths = catalog.Entries.Select(entry => entry.AssetPath).ToArray(),
                trainingReviewBundlePath = trainingBundle?.sourcePath,
                trainingReviewBundleStatus = trainingBundle == null ? "not_linked" : "linked",
                truthCaptureMode = trainingBundle?.truthCaptureMode,
                trainingLinkedPrefabCount = catalog.Entries.Count(entry => !string.IsNullOrWhiteSpace(entry.CandidateId)),
            };
            File.WriteAllText(Path.Combine(absoluteOutput, "vfx_web_build_manifest.json"), JsonUtility.ToJson(manifest, true) + "\n");
            Debug.Log($"VFX Web Prefab Player build succeeded: {catalog.Entries.Count} Prefabs -> {absoluteOutput}");
        }

        private static VfxWebCatalog PrepareAssets(TrainingReviewBundle trainingBundle)
        {
            EnsureFolder(GeneratedPrefabRoot);
            EnsureFolder(Path.GetDirectoryName(ScenePath).Replace('\\', '/'));

            var entries = BuildCatalogEntries(trainingBundle);
            var catalog = AssetDatabase.LoadAssetAtPath<VfxWebCatalog>(CatalogPath);
            if (catalog == null)
            {
                catalog = ScriptableObject.CreateInstance<VfxWebCatalog>();
                AssetDatabase.CreateAsset(catalog, CatalogPath);
            }

            catalog.ReplaceEntries(entries);
            EditorUtility.SetDirty(catalog);
            CreatePreviewScene(catalog);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            return catalog;
        }

        private static List<VfxWebCatalog.Entry> BuildCatalogEntries(TrainingReviewBundle trainingBundle)
        {
            var paths = new HashSet<string>(StringComparer.Ordinal);
            if (trainingBundle?.entries != null && trainingBundle.entries.Length > 0)
            {
                foreach (var training in trainingBundle.entries)
                {
                    var mappedPath = !string.IsNullOrWhiteSpace(training.webPrefabPath)
                        ? training.webPrefabPath
                        : training.sourcePrefabPath;
                    paths.Add(mappedPath.Replace('\\', '/'));
                }
            }
            else
            {
                foreach (var searchRoot in PrefabSearchRoots)
                {
                    if (!AssetDatabase.IsValidFolder(searchRoot))
                        continue;
                    foreach (var guid in AssetDatabase.FindAssets("t:Prefab", new[] { searchRoot }))
                        paths.Add(AssetDatabase.GUIDToAssetPath(guid));
                }
            }

            var trainingByPrefab = BuildTrainingEntryIndex(trainingBundle);
            var matchedTrainingEntries = new HashSet<TrainingReviewEntry>();
            var entries = new List<VfxWebCatalog.Entry>();
            foreach (var path in paths.OrderBy(item => item, StringComparer.Ordinal))
            {
                if (trainingBundle == null && entries.Count >= DefaultPreviewLimit)
                    break;
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (prefab == null)
                {
                    if (trainingBundle != null)
                        throw new InvalidOperationException("Training review Prefab was not found in EffectDemo 2022: " + path);
                    continue;
                }

                var particleSystems = prefab.GetComponentsInChildren<ParticleSystem>(true);
                var renderers = prefab.GetComponentsInChildren<Renderer>(true);
                if (particleSystems.Length == 0 && renderers.Length == 0)
                    continue;

                var missingScripts = prefab.GetComponentsInChildren<Component>(true).Count(component => component == null);
                var missingMaterials = renderers.Sum(renderer => renderer.sharedMaterials.Count(material => material == null));
                var status = missingScripts == 0 && missingMaterials == 0 ? "direct" : "context_required";
                var duration = EstimateDuration(particleSystems);
                var sourcePath = path;
                trainingByPrefab.TryGetValue(path, out var training);
                if (training == null)
                    trainingByPrefab.TryGetValue(sourcePath, out training);
                if (training != null)
                    matchedTrainingEntries.Add(training);

                entries.Add(new VfxWebCatalog.Entry(
                    AssetDatabase.AssetPathToGUID(path),
                    prefab.name,
                    ResolveCategory(path),
                    path,
                    sourcePath,
                    status,
                    prefab,
                    particleSystems.Length,
                    renderers.Length,
                    duration,
                    training?.runId ?? trainingBundle?.runId,
                    training?.candidateId,
                    training?.trainingCaseId,
                    training?.effectFamily,
                    training?.materialTimelinePath,
                    training?.materialTimelineStatus ?? "not_linked",
                    training?.materialChangeCount ?? 0,
                    training?.materialKeyTimes ?? Array.Empty<float>(),
                    training?.sourceScriptFidelity ?? "unknown",
                    training?.specPath,
                    training?.renderManifestPath,
                    training?.hasSeed ?? false,
                    training?.seed ?? 0,
                    training?.generator,
                    training?.generatorVersion));
            }

            var minimumCount = trainingBundle == null ? 4 : 1;
            if (entries.Count < minimumCount)
                throw new InvalidOperationException($"Expected at least {minimumCount} renderable Prefabs, found {entries.Count}.");
            var requestedTrainingEntries = trainingBundle?.entries?.Length ?? 0;
            if (matchedTrainingEntries.Count != requestedTrainingEntries)
                throw new InvalidOperationException($"Training review bundle mapped {matchedTrainingEntries.Count}/{requestedTrainingEntries} entries into the WebGL catalog.");

            return entries;
        }

        private static Dictionary<string, TrainingReviewEntry> BuildTrainingEntryIndex(TrainingReviewBundle trainingBundle)
        {
            var result = new Dictionary<string, TrainingReviewEntry>(StringComparer.OrdinalIgnoreCase);
            foreach (var entry in trainingBundle?.entries ?? Array.Empty<TrainingReviewEntry>())
            {
                AddTrainingEntryPath(result, entry.webPrefabPath, entry);
                AddTrainingEntryPath(result, entry.sourcePrefabPath, entry);
            }
            return result;
        }

        private static void AddTrainingEntryPath(Dictionary<string, TrainingReviewEntry> index, string path, TrainingReviewEntry entry)
        {
            if (string.IsNullOrWhiteSpace(path))
                return;
            var normalized = path.Replace('\\', '/');
            if (index.TryGetValue(normalized, out var existing) && !ReferenceEquals(existing, entry))
                throw new InvalidOperationException("Training review bundle maps multiple candidates to the same Prefab: " + normalized);
            index[normalized] = entry;
        }

        private static TrainingReviewBundle LoadTrainingReviewBundle()
        {
            var path = Environment.GetEnvironmentVariable("VFX_WEB_TRAINING_REVIEW_BUNDLE");
            if (string.IsNullOrWhiteSpace(path))
                path = ReadCommandLineValue("-trainingReviewBundle");
            if (string.IsNullOrWhiteSpace(path))
                return null;

            var absolutePath = Path.GetFullPath(path);
            if (!File.Exists(absolutePath))
                throw new FileNotFoundException("Training review bundle was not found.", absolutePath);
            var bundle = JsonUtility.FromJson<TrainingReviewBundle>(File.ReadAllText(absolutePath));
            if (bundle == null || bundle.schemaVersion != "vfx_web_training_review_bundle.v1")
                throw new InvalidOperationException("Unsupported training review bundle: " + absolutePath);
            var projectRoot = Directory.GetParent(Application.dataPath).FullName;
            var authoritativeProject = Environment.GetEnvironmentVariable("VFX_WEB_AUTHORITATIVE_PROJECT");
            if (string.IsNullOrWhiteSpace(authoritativeProject))
                authoritativeProject = projectRoot;
            authoritativeProject = Path.GetFullPath(authoritativeProject);
            var sourceProject = Path.GetFullPath(bundle.sourceUnityProject ?? string.Empty);
            if (!string.Equals(authoritativeProject.TrimEnd('\\', '/'), sourceProject.TrimEnd('\\', '/'), StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Training review bundle does not belong to EffectDemo 2022: " + sourceProject);
            if (!string.Equals(bundle.truthCaptureMode, "play_mode_runtime", StringComparison.Ordinal))
                throw new InvalidOperationException("WebGL training review requires EffectDemo play_mode_runtime truth evidence.");
            bundle.sourcePath = absolutePath.Replace('\\', '/');
            foreach (var entry in bundle.entries ?? Array.Empty<TrainingReviewEntry>())
            {
                if (string.IsNullOrWhiteSpace(entry.candidateId))
                    throw new InvalidOperationException("Training review bundle contains an empty candidateId.");
                if (string.IsNullOrWhiteSpace(entry.webPrefabPath) && string.IsNullOrWhiteSpace(entry.sourcePrefabPath))
                    throw new InvalidOperationException("Training review entry must map a webPrefabPath or sourcePrefabPath: " + entry.candidateId);
                if (!string.Equals(entry.materialTimelineStatus, "ready", StringComparison.Ordinal))
                    throw new InvalidOperationException("Training review entry has no ready material timeline: " + entry.candidateId);
            }
            return bundle;
        }

        private static float EstimateDuration(IEnumerable<ParticleSystem> particleSystems)
        {
            var duration = 1.5f;
            foreach (var particleSystem in particleSystems)
            {
                var main = particleSystem.main;
                duration = Mathf.Max(duration, main.duration + main.startDelay.constantMax + main.startLifetime.constantMax);
            }
            return Mathf.Clamp(duration, 1.5f, 10f);
        }

        private static string ResolveCategory(string path)
        {
            if (path.IndexOf("/FX/UI/", StringComparison.OrdinalIgnoreCase) >= 0)
                return "UI";
            if (path.IndexOf("/FX/Enemy/", StringComparison.OrdinalIgnoreCase) >= 0)
                return "Enemy";
            if (path.IndexOf("/FX/Battle/", StringComparison.OrdinalIgnoreCase) >= 0)
                return "Battle";
            return "Trains";
        }

        private static void CreatePreviewScene(VfxWebCatalog catalog)
        {
            var setup = EditorSceneManager.GetSceneManagerSetup();
            try
            {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

                var cameraObject = new GameObject("Main Camera");
                cameraObject.tag = "MainCamera";
                var camera = cameraObject.AddComponent<Camera>();
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(0.055f, 0.065f, 0.07f, 1f);
                camera.fieldOfView = 42f;
                camera.nearClipPlane = 0.05f;
                camera.farClipPlane = 250f;
                camera.allowHDR = false;
                cameraObject.AddComponent<AudioListener>();

                var lightObject = new GameObject("Key Light");
                var light = lightObject.AddComponent<Light>();
                light.type = LightType.Directional;
                light.color = new Color(1f, 0.96f, 0.9f, 1f);
                light.intensity = 1.1f;
                lightObject.transform.rotation = Quaternion.Euler(42f, -35f, 0f);

                var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
                ground.name = "Ground";
                ground.transform.position = new Vector3(0f, -1.25f, 0f);
                ground.transform.localScale = new Vector3(2.4f, 1f, 2.4f);
                UnityEngine.Object.DestroyImmediate(ground.GetComponent<Collider>());
                var groundRenderer = ground.GetComponent<Renderer>();
                groundRenderer.sharedMaterial = CreateGroundMaterial();

                var playerObject = new GameObject("VfxWebPlayer");
                var previewRoot = new GameObject("PreviewRoot").transform;
                previewRoot.SetParent(playerObject.transform, false);
                var player = playerObject.AddComponent<VfxWebPlayer>();
                player.Configure(catalog, previewRoot, camera, groundRenderer);

                EditorSceneManager.SaveScene(scene, ScenePath);
            }
            finally
            {
                if (setup.Length > 0)
                    EditorSceneManager.RestoreSceneManagerSetup(setup);
            }
        }

        private static Material CreateGroundMaterial()
        {
            var material = AssetDatabase.LoadAssetAtPath<Material>(GroundMaterialPath);
            if (material == null)
            {
                var shader = Shader.Find("Unlit/Color") ?? Shader.Find("Standard");
                if (shader == null)
                    throw new InvalidOperationException("A built-in ground shader was not found.");
                material = new Material(shader) { name = "M_VfxWebGround" };
                AssetDatabase.CreateAsset(material, GroundMaterialPath);
            }

            if (material.HasProperty("_BaseColor"))
                material.SetColor("_BaseColor", new Color(0.09f, 0.1f, 0.105f, 1f));
            if (material.HasProperty("_Color"))
                material.SetColor("_Color", new Color(0.09f, 0.1f, 0.105f, 1f));
            EditorUtility.SetDirty(material);
            return material;
        }

        private static string ReadCommandLineValue(string key)
        {
            var args = Environment.GetCommandLineArgs();
            for (var index = 0; index < args.Length - 1; index++)
            {
                if (string.Equals(args[index], key, StringComparison.OrdinalIgnoreCase))
                    return args[index + 1];
            }
            return null;
        }

        private static void EnsureFolder(string path)
        {
            var normalized = path.Replace('\\', '/');
            var parts = normalized.Split('/');
            var current = parts[0];
            for (var index = 1; index < parts.Length; index++)
            {
                var next = current + "/" + parts[index];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, parts[index]);
                current = next;
            }
        }
    }
}
