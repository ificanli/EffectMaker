using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Playables;
using UnityEngine.Rendering;

namespace VfxPrefabWeb
{
    public sealed class VfxWebPlayer : MonoBehaviour
    {
        [Serializable]
        private sealed class CatalogItemDto
        {
            public string id;
            public string name;
            public string category;
            public string assetPath;
            public string sourcePath;
            public string playability;
            public int particleSystemCount;
            public int rendererCount;
            public float suggestedDuration;
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

        [Serializable]
        private sealed class SelectionDto
        {
            public string id;
            public string name;
            public string category;
            public string assetPath;
            public string sourcePath;
            public string playability;
        }

        [Serializable]
        private sealed class RuntimeDto
        {
            public string id;
            public bool paused;
            public float speed;
            public float elapsed;
            public int liveParticles;
            public int activeRenderers;
            public int materialSlots;
            public string materialStateFingerprint;
            public int webglMaterialStateChanges;
            public float yaw;
            public float pitch;
            public float distance;
            public string background;
        }

        [Serializable]
        private sealed class BrowserEvent
        {
            public string type;
            public string message;
            public CatalogItemDto[] catalog;
            public SelectionDto selection;
            public RuntimeDto runtime;
        }

        [SerializeField] private VfxWebCatalog catalog;
        [SerializeField] private Transform previewRoot;
        [SerializeField] private Camera previewCamera;
        [SerializeField] private Renderer groundRenderer;

        private GameObject currentInstance;
        private VfxWebCatalog.Entry currentEntry;
        private Material groundMaterial;
        private Vector3 viewTarget = new Vector3(0f, 0.5f, 0f);
        private float yaw = 18f;
        private float pitch = 9f;
        private float distance = 8f;
        private float speed = 1f;
        private float playbackElapsed;
        private float lastUnscaledTime;
        private float nextRuntimeEventAt;
        private bool paused;
        private string background = "#0e1112";
        private string lastMaterialStateFingerprint;
        private int webglMaterialStateChanges;
        private Coroutine replayAtRoutine;

        public void Configure(VfxWebCatalog configuredCatalog, Transform configuredRoot, Camera configuredCamera, Renderer configuredGround)
        {
            catalog = configuredCatalog;
            previewRoot = configuredRoot;
            previewCamera = configuredCamera;
            groundRenderer = configuredGround;
        }

        private void Awake()
        {
            if (previewRoot == null)
            {
                var root = new GameObject("PreviewRoot");
                root.transform.SetParent(transform, false);
                previewRoot = root.transform;
            }

            if (previewCamera == null)
                previewCamera = Camera.main;

            if (groundRenderer != null)
                groundMaterial = groundRenderer.material;

            lastUnscaledTime = Time.unscaledTime;
            ApplyCameraTransform();
        }

        private void Start()
        {
            EmitCatalog();
            Emit(new BrowserEvent { type = "ready" });

            if (catalog != null && catalog.Entries.Count > 0)
            {
                var initialEntry = catalog.Entries[0];
                var requestedCatalogId = GetQueryParameter(Application.absoluteURL, "catalogId");
                if (!string.IsNullOrWhiteSpace(requestedCatalogId))
                {
                    foreach (var entry in catalog.Entries)
                    {
                        if (string.Equals(entry.Id, requestedCatalogId, StringComparison.Ordinal))
                        {
                            initialEntry = entry;
                            break;
                        }
                    }
                }
                else
                {
                    foreach (var entry in catalog.Entries)
                    {
                        if (string.Equals(entry.Category, "Blade", StringComparison.Ordinal))
                        {
                            initialEntry = entry;
                            break;
                        }
                    }
                }
                SelectEffect(initialEntry.Id);
            }
            else
                EmitError("No playable Prefabs were included in this build.");
        }

        private static string GetQueryParameter(string absoluteUrl, string key)
        {
            if (string.IsNullOrWhiteSpace(absoluteUrl) || string.IsNullOrWhiteSpace(key))
                return string.Empty;
            var queryStart = absoluteUrl.IndexOf('?', StringComparison.Ordinal);
            if (queryStart < 0 || queryStart >= absoluteUrl.Length - 1)
                return string.Empty;
            var query = absoluteUrl.Substring(queryStart + 1).Split('#')[0];
            foreach (var part in query.Split('&'))
            {
                var separator = part.IndexOf('=');
                var name = separator < 0 ? part : part.Substring(0, separator);
                if (!string.Equals(Uri.UnescapeDataString(name), key, StringComparison.Ordinal))
                    continue;
                return separator < 0 ? string.Empty : Uri.UnescapeDataString(part.Substring(separator + 1));
            }
            return string.Empty;
        }

        private void Update()
        {
            AccumulatePlaybackTime();
            if (Time.unscaledTime < nextRuntimeEventAt)
                return;

            nextRuntimeEventAt = Time.unscaledTime + 0.25f;
            EmitRuntimeState();
        }

        private void OnDestroy()
        {
            Time.timeScale = 1f;
        }

        public void RequestState(string unused)
        {
            EmitCatalog();
            EmitSelection();
            EmitRuntimeState();
        }

        public void SelectEffect(string id)
        {
            if (catalog == null)
            {
                EmitError("The Prefab catalog is not configured.");
                return;
            }

            VfxWebCatalog.Entry selected = null;
            foreach (var entry in catalog.Entries)
            {
                if (string.Equals(entry.Id, id, StringComparison.Ordinal))
                {
                    selected = entry;
                    break;
                }
            }

            if (selected == null || selected.Prefab == null)
            {
                EmitError("Prefab was not found in this build: " + id);
                return;
            }

            currentEntry = selected;
            SpawnCurrent();
        }

        public void Replay(string unused)
        {
            if (currentEntry != null)
                SpawnCurrent();
        }

        public void ReplayAt(string value)
        {
            if (!float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var seconds))
                return;
            if (replayAtRoutine != null)
                StopCoroutine(replayAtRoutine);
            replayAtRoutine = StartCoroutine(ReplayAndPauseAt(Mathf.Clamp(seconds, 0f, 30f)));
        }

        public void SetPaused(string value)
        {
            AccumulatePlaybackTime();
            if (!bool.TryParse(value, out paused))
                paused = value == "1";

            ApplyPlaybackState();
            EmitRuntimeState();
        }

        public void SetTimeScale(string value)
        {
            if (!float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed))
                return;

            AccumulatePlaybackTime();
            speed = Mathf.Clamp(parsed, 0.1f, 4f);
            ApplyPlaybackState();
            EmitRuntimeState();
        }

        public void Orbit(string payload)
        {
            var parts = payload.Split(',');
            if (parts.Length != 2)
                return;

            if (!float.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var deltaX))
                return;
            if (!float.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var deltaY))
                return;

            yaw += deltaX * 0.18f;
            pitch = Mathf.Clamp(pitch - deltaY * 0.14f, -35f, 75f);
            ApplyCameraTransform();
        }

        public void Zoom(string payload)
        {
            if (!float.TryParse(payload, NumberStyles.Float, CultureInfo.InvariantCulture, out var delta))
                return;

            distance = Mathf.Clamp(distance * Mathf.Exp(delta * 0.0015f), 1.2f, 45f);
            ApplyCameraTransform();
        }

        public void FitView(string unused)
        {
            if (!TryGetCurrentBounds(out var bounds))
            {
                viewTarget = new Vector3(0f, 0.5f, 0f);
                distance = 8f;
                ApplyCameraTransform();
                return;
            }

            viewTarget = bounds.center;
            var radius = Mathf.Max(bounds.extents.x, bounds.extents.y, bounds.extents.z, 0.5f);
            var halfFov = Mathf.Max(10f, previewCamera.fieldOfView * 0.5f) * Mathf.Deg2Rad;
            distance = Mathf.Clamp(radius / Mathf.Tan(halfFov) * 1.35f, 1.5f, 45f);
            ApplyCameraTransform();
        }

        public void ResetView(string unused)
        {
            yaw = 18f;
            pitch = 9f;
            FitView(string.Empty);
        }

        public void SetBackground(string htmlColor)
        {
            if (!htmlColor.StartsWith("#", StringComparison.Ordinal))
                htmlColor = "#" + htmlColor;

            if (!ColorUtility.TryParseHtmlString(htmlColor, out var color))
                return;

            if (previewCamera != null)
                previewCamera.backgroundColor = color;
            background = "#" + ColorUtility.ToHtmlStringRGB(color).ToLowerInvariant();

            if (groundMaterial != null)
            {
                var groundColor = Color.Lerp(color, Color.white, color.maxColorComponent > 0.5f ? 0.02f : 0.09f);
                if (groundMaterial.HasProperty("_BaseColor"))
                    groundMaterial.SetColor("_BaseColor", groundColor);
                else if (groundMaterial.HasProperty("_Color"))
                    groundMaterial.SetColor("_Color", groundColor);
            }
        }

        private void SpawnCurrent()
        {
            if (currentInstance != null)
                Destroy(currentInstance);

            currentInstance = Instantiate(currentEntry.Prefab, previewRoot, false);
            currentInstance.name = currentEntry.DisplayName;
            currentInstance.transform.localPosition = Vector3.zero;
            currentInstance.SetActive(true);
            playbackElapsed = 0f;
            lastUnscaledTime = Time.unscaledTime;
            lastMaterialStateFingerprint = null;
            webglMaterialStateChanges = 0;

            foreach (var trail in currentInstance.GetComponentsInChildren<TrailRenderer>(true))
                trail.Clear();

            foreach (var animator in currentInstance.GetComponentsInChildren<Animator>(true))
            {
                animator.Rebind();
                animator.Update(0f);
            }

            foreach (var director in currentInstance.GetComponentsInChildren<PlayableDirector>(true))
            {
                if (director.playableAsset == null)
                    continue;
                director.time = 0d;
                director.Evaluate();
                director.Play();
            }

            foreach (var particleSystem in currentInstance.GetComponentsInChildren<ParticleSystem>(true))
            {
                particleSystem.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
                particleSystem.Play(true);
            }

            ApplyPlaybackState();
            EmitSelection();
            EmitRuntimeState();
        }

        private IEnumerator ReplayAndPauseAt(float seconds)
        {
            paused = false;
            SpawnCurrent();
            while (playbackElapsed + 0.0001f < seconds)
                yield return null;
            paused = true;
            ApplyPlaybackState();
            EmitRuntimeState();
            replayAtRoutine = null;
        }

        private void ApplyPlaybackState()
        {
            Time.timeScale = paused ? 0f : speed;
            if (currentInstance == null)
                return;

            if (paused)
            {
                foreach (var particleSystem in currentInstance.GetComponentsInChildren<ParticleSystem>(true))
                    particleSystem.Pause(true);
                foreach (var director in currentInstance.GetComponentsInChildren<PlayableDirector>(true))
                    director.Pause();
            }
            else
            {
                foreach (var particleSystem in currentInstance.GetComponentsInChildren<ParticleSystem>(true))
                    particleSystem.Play(true);
                foreach (var director in currentInstance.GetComponentsInChildren<PlayableDirector>(true))
                {
                    if (director.playableAsset != null)
                        director.Resume();
                }
            }
        }

        private void AccumulatePlaybackTime()
        {
            var now = Time.unscaledTime;
            if (!paused)
                playbackElapsed += Mathf.Max(0f, now - lastUnscaledTime) * speed;
            lastUnscaledTime = now;
        }

        private bool TryGetCurrentBounds(out Bounds bounds)
        {
            bounds = default;
            if (currentInstance == null)
                return false;

            var initialized = false;
            foreach (var itemRenderer in currentInstance.GetComponentsInChildren<Renderer>(true))
            {
                if (!itemRenderer.enabled || !itemRenderer.gameObject.activeInHierarchy)
                    continue;

                var itemBounds = itemRenderer.bounds;
                if (!IsFinite(itemBounds.center) || !IsFinite(itemBounds.extents))
                    continue;
                if (itemBounds.extents.magnitude > 500f)
                    continue;

                if (!initialized)
                {
                    bounds = itemBounds;
                    initialized = true;
                }
                else
                {
                    bounds.Encapsulate(itemBounds);
                }
            }

            return initialized;
        }

        private static bool IsFinite(Vector3 value)
        {
            return !float.IsNaN(value.x) && !float.IsInfinity(value.x)
                && !float.IsNaN(value.y) && !float.IsInfinity(value.y)
                && !float.IsNaN(value.z) && !float.IsInfinity(value.z);
        }

        private void ApplyCameraTransform()
        {
            if (previewCamera == null)
                return;

            var rotation = Quaternion.Euler(pitch, yaw, 0f);
            previewCamera.transform.position = viewTarget + rotation * new Vector3(0f, 0f, -distance);
            previewCamera.transform.rotation = rotation;
        }

        private void EmitCatalog()
        {
            var items = new List<CatalogItemDto>();
            if (catalog != null)
            {
                foreach (var entry in catalog.Entries)
                {
                    items.Add(new CatalogItemDto
                    {
                        id = entry.Id,
                        name = entry.DisplayName,
                        category = entry.Category,
                        assetPath = entry.AssetPath,
                        sourcePath = entry.SourcePath,
                        playability = entry.Playability,
                        particleSystemCount = entry.ParticleSystemCount,
                        rendererCount = entry.RendererCount,
                        suggestedDuration = entry.SuggestedDuration,
                        runId = entry.RunId,
                        candidateId = entry.CandidateId,
                        trainingCaseId = entry.TrainingCaseId,
                        effectFamily = entry.EffectFamily,
                        materialTimelinePath = entry.MaterialTimelinePath,
                        materialTimelineStatus = entry.MaterialTimelineStatus,
                        materialChangeCount = entry.MaterialChangeCount,
                        materialKeyTimes = entry.MaterialKeyTimes,
                        sourceScriptFidelity = entry.SourceScriptFidelity,
                        specPath = entry.SpecPath,
                        renderManifestPath = entry.RenderManifestPath,
                        hasSeed = entry.HasSeed,
                        seed = entry.Seed,
                        generator = entry.Generator,
                        generatorVersion = entry.GeneratorVersion,
                    });
                }
            }

            Emit(new BrowserEvent { type = "catalog", catalog = items.ToArray() });
        }

        private void EmitSelection()
        {
            if (currentEntry == null)
                return;

            Emit(new BrowserEvent
            {
                type = "selection",
                selection = new SelectionDto
                {
                    id = currentEntry.Id,
                    name = currentEntry.DisplayName,
                    category = currentEntry.Category,
                    assetPath = currentEntry.AssetPath,
                    sourcePath = currentEntry.SourcePath,
                    playability = currentEntry.Playability,
                },
            });
        }

        private void EmitRuntimeState()
        {
            if (currentEntry == null)
                return;

            var liveParticles = 0;
            var activeRenderers = 0;
            var materialSlots = 0;
            var materialStateFingerprint = "0000000000000000";
            if (currentInstance != null)
            {
                foreach (var particleSystem in currentInstance.GetComponentsInChildren<ParticleSystem>(true))
                    liveParticles += particleSystem.particleCount;
                foreach (var itemRenderer in currentInstance.GetComponentsInChildren<Renderer>(true))
                {
                    if (itemRenderer.enabled && itemRenderer.gameObject.activeInHierarchy)
                        activeRenderers++;
                }
                materialStateFingerprint = ComputeMaterialStateFingerprint(currentInstance, out materialSlots);
                if (!string.IsNullOrEmpty(lastMaterialStateFingerprint)
                    && !string.Equals(lastMaterialStateFingerprint, materialStateFingerprint, StringComparison.Ordinal))
                    webglMaterialStateChanges++;
                lastMaterialStateFingerprint = materialStateFingerprint;
            }

            Emit(new BrowserEvent
            {
                type = "runtime",
                runtime = new RuntimeDto
                {
                    id = currentEntry.Id,
                    paused = paused,
                    speed = speed,
                    elapsed = playbackElapsed,
                    liveParticles = liveParticles,
                    activeRenderers = activeRenderers,
                    materialSlots = materialSlots,
                    materialStateFingerprint = materialStateFingerprint,
                    webglMaterialStateChanges = webglMaterialStateChanges,
                    yaw = yaw,
                    pitch = pitch,
                    distance = distance,
                    background = background,
                },
            });
        }

        private static string ComputeMaterialStateFingerprint(GameObject root, out int materialSlotCount)
        {
            var hash = 1469598103934665603UL;
            materialSlotCount = 0;
            var propertyBlock = new MaterialPropertyBlock();
            foreach (var itemRenderer in root.GetComponentsInChildren<Renderer>(true))
            {
                AddHash(ref hash, itemRenderer.name);
                AddHash(ref hash, itemRenderer.enabled ? "1" : "0");
                var materials = itemRenderer.sharedMaterials;
                for (var slot = 0; slot < materials.Length; slot++)
                {
                    materialSlotCount++;
                    var material = materials[slot];
                    AddHash(ref hash, slot.ToString(CultureInfo.InvariantCulture));
                    if (material == null || material.shader == null)
                    {
                        AddHash(ref hash, "missing");
                        continue;
                    }

                    AddHash(ref hash, RuntimeObjectId(material));
                    AddHash(ref hash, material.shader.name);
                    AddHash(ref hash, material.renderQueue.ToString(CultureInfo.InvariantCulture));
                    var keywords = material.shaderKeywords;
                    Array.Sort(keywords, StringComparer.Ordinal);
                    foreach (var keyword in keywords)
                        AddHash(ref hash, keyword);

                    propertyBlock.Clear();
                    itemRenderer.GetPropertyBlock(propertyBlock, slot);
                    var shader = material.shader;
                    for (var propertyIndex = 0; propertyIndex < shader.GetPropertyCount(); propertyIndex++)
                    {
                        var propertyId = shader.GetPropertyNameId(propertyIndex);
                        var propertyName = shader.GetPropertyName(propertyIndex);
                        var propertyType = shader.GetPropertyType(propertyIndex);
                        AddHash(ref hash, propertyName);
                        AddMaterialPropertyHash(ref hash, material, propertyId, propertyType);
                        AddPropertyBlockHash(ref hash, propertyBlock, propertyId, propertyType);
                    }
                }
            }
            return hash.ToString("x16", CultureInfo.InvariantCulture);
        }

        private static void AddMaterialPropertyHash(ref ulong hash, Material material, int propertyId, ShaderPropertyType propertyType)
        {
            switch (propertyType)
            {
                case ShaderPropertyType.Color:
                    AddHash(ref hash, material.GetColor(propertyId).ToString("F5"));
                    break;
                case ShaderPropertyType.Vector:
                    AddHash(ref hash, material.GetVector(propertyId).ToString("F5"));
                    break;
                case ShaderPropertyType.Float:
                case ShaderPropertyType.Range:
                    AddHash(ref hash, material.GetFloat(propertyId).ToString("G7", CultureInfo.InvariantCulture));
                    break;
                case ShaderPropertyType.Int:
                    AddHash(ref hash, material.GetInteger(propertyId).ToString(CultureInfo.InvariantCulture));
                    break;
                case ShaderPropertyType.Texture:
                    var texture = material.GetTexture(propertyId);
                    AddHash(ref hash, RuntimeObjectId(texture));
                    AddHash(ref hash, material.GetTextureScale(propertyId).ToString("F5"));
                    AddHash(ref hash, material.GetTextureOffset(propertyId).ToString("F5"));
                    break;
            }
        }

        private static void AddPropertyBlockHash(ref ulong hash, MaterialPropertyBlock block, int propertyId, ShaderPropertyType propertyType)
        {
            if (block.isEmpty || !block.HasProperty(propertyId))
                return;
            AddHash(ref hash, "mpb");
            switch (propertyType)
            {
                case ShaderPropertyType.Color:
                    AddHash(ref hash, block.GetColor(propertyId).ToString("F5"));
                    break;
                case ShaderPropertyType.Vector:
                    AddHash(ref hash, block.GetVector(propertyId).ToString("F5"));
                    break;
                case ShaderPropertyType.Float:
                case ShaderPropertyType.Range:
                    AddHash(ref hash, block.GetFloat(propertyId).ToString("G7", CultureInfo.InvariantCulture));
                    break;
                case ShaderPropertyType.Int:
                    AddHash(ref hash, block.GetInteger(propertyId).ToString(CultureInfo.InvariantCulture));
                    break;
                case ShaderPropertyType.Texture:
                    var texture = block.GetTexture(propertyId);
                    AddHash(ref hash, RuntimeObjectId(texture));
                    break;
            }
        }

        private static void AddHash(ref ulong hash, string value)
        {
            foreach (var character in value ?? string.Empty)
            {
                hash ^= character;
                hash *= 1099511628211UL;
            }
        }

        private static string RuntimeObjectId(UnityEngine.Object value)
        {
            if (value == null)
                return "null";
#if UNITY_6000_0_OR_NEWER
            return value.GetEntityId().ToString();
#else
            return value.GetInstanceID().ToString(CultureInfo.InvariantCulture);
#endif
        }

        private static void EmitError(string message)
        {
            Emit(new BrowserEvent { type = "error", message = message });
        }

        private static void Emit(BrowserEvent browserEvent)
        {
            VfxWebBridge.Dispatch(JsonUtility.ToJson(browserEvent));
        }

        private static class VfxWebBridge
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            [DllImport("__Internal")]
            private static extern void VfxWebDispatch(string json);
#endif

            public static void Dispatch(string json)
            {
#if UNITY_WEBGL && !UNITY_EDITOR
                VfxWebDispatch(json);
#else
                Debug.Log("[VfxWebPlayer] " + json);
#endif
            }
        }
    }
}
