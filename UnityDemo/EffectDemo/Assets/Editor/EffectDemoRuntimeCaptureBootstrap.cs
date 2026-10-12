using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class EffectDemoRuntimeCaptureBootstrap
{
    private const string RequestsEnvironment = "EFFECTDEMO_SOURCE_RENDER_REQUESTS";
    private const string RequestSchema = "effectdemo_source_render_requests.v1";

    public static void StartFromEnvironment()
    {
        var requestPath = Environment.GetEnvironmentVariable(RequestsEnvironment);
        if (string.IsNullOrWhiteSpace(requestPath) || !File.Exists(requestPath))
            throw new InvalidOperationException($"Set {RequestsEnvironment} to an existing adaptive render request.");
        var request = JsonUtility.FromJson<EffectDemoRuntimeCaptureController.RequestManifest>(File.ReadAllText(requestPath));
        if (request == null || request.schema_version != RequestSchema || request.sampling_mode != "adaptive_runtime")
            throw new InvalidOperationException($"Adaptive runtime request expected: {requestPath}");

        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var controllerObject = new GameObject("EffectDemoRuntimeCaptureController");
        var controller = controllerObject.AddComponent<EffectDemoRuntimeCaptureController>();
        var candidateParent = new GameObject("RuntimeCaptureCandidates");
        var entries = new List<EffectDemoRuntimeCaptureController.CandidateEntry>();
        foreach (var item in request.requests ?? Array.Empty<EffectDemoRuntimeCaptureController.RequestItem>())
        {
            var isMaterialStateProbe = item.prefab_path == EffectDemoMaterialStateProbeFactory.PrefabPath;
            var runtimeFactoryId = EffectDemoRuntimeCaptureRegressionProbeFactory.CanCreate(item.prefab_path) ? item.prefab_path : null;
            var prefab = isMaterialStateProbe || runtimeFactoryId != null ? null : AssetDatabase.LoadAssetAtPath<GameObject>(item.prefab_path);
            entries.Add(new EffectDemoRuntimeCaptureController.CandidateEntry
            {
                request = item,
                prefab_asset = prefab,
                use_material_state_probe_factory = isMaterialStateProbe,
                runtime_factory_id = runtimeFactoryId,
            });
        }
        controller.Configure(request, entries.ToArray(), candidateParent.transform);
        EditorApplication.EnterPlaymode();
    }
}
