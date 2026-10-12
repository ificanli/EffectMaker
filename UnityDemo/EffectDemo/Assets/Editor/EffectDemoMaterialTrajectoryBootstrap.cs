using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class EffectDemoMaterialTrajectoryBootstrap
{
    private const string RequestsEnvironment = "EFFECTDEMO_MATERIAL_TRAJECTORY_REQUESTS";

    public static void StartFromEnvironment()
    {
        var requestPath = Environment.GetEnvironmentVariable(RequestsEnvironment);
        if (string.IsNullOrWhiteSpace(requestPath) || !File.Exists(requestPath))
            throw new InvalidOperationException($"Set {RequestsEnvironment} to an existing material trajectory request.");

        var request = JsonUtility.FromJson<EffectDemoMaterialTrajectoryExecutor.RequestManifest>(File.ReadAllText(requestPath));
        if (request == null || request.schema_version != EffectDemoMaterialTrajectoryExecutor.RequestSchema)
            throw new InvalidOperationException($"Unsupported material trajectory request: {requestPath}");

        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var controllerObject = new GameObject("EffectDemoMaterialTrajectoryExecutor");
        var controller = controllerObject.AddComponent<EffectDemoMaterialTrajectoryExecutor>();
        var prepared = new List<EffectDemoMaterialTrajectoryExecutor.PreparedItem>();
        foreach (var item in request.requests ?? Array.Empty<EffectDemoMaterialTrajectoryExecutor.RequestItem>())
            prepared.Add(Prepare(item));
        controller.Configure(request, prepared.ToArray());
        EditorApplication.EnterPlaymode();
    }

    private static EffectDemoMaterialTrajectoryExecutor.PreparedItem Prepare(EffectDemoMaterialTrajectoryExecutor.RequestItem request)
    {
        var prepared = new EffectDemoMaterialTrajectoryExecutor.PreparedItem { request = request };
        try
        {
            if (request == null || string.IsNullOrWhiteSpace(request.spec_path) || !File.Exists(request.spec_path))
                throw new InvalidOperationException($"Trajectory spec does not exist: {request?.spec_path}");
            var spec = JsonUtility.FromJson<EffectDemoMaterialTrajectoryExecutor.MaterialTrajectorySpec>(File.ReadAllText(request.spec_path));
            if (spec == null)
                throw new InvalidOperationException($"Trajectory spec could not be parsed: {request.spec_path}");
            ApplyTrackClamps(request, spec);
            spec.has_negative_mutation = request.has_negative_mutation;
            if (!request.has_negative_mutation)
                spec.negative_mutation = null;
            prepared.spec = spec;
            prepared.source_material = AssetDatabase.LoadAssetAtPath<Material>(spec.source_asset?.material_path);
            prepared.prefab_asset = string.IsNullOrWhiteSpace(request.prefab_path) ? null : AssetDatabase.LoadAssetAtPath<GameObject>(request.prefab_path);
            if (!string.IsNullOrWhiteSpace(request.prefab_path) && prepared.prefab_asset == null)
                throw new InvalidOperationException($"Prompt composition Prefab could not be loaded: {request.prefab_path}");

            var textureEvents = new List<EffectDemoMaterialTrajectoryExecutor.PreparedTextureEvent>();
            foreach (var item in spec.texture_swap_events ?? Array.Empty<EffectDemoMaterialTrajectoryExecutor.TextureSwapEvent>())
            {
                textureEvents.Add(new EffectDemoMaterialTrajectoryExecutor.PreparedTextureEvent
                {
                    definition = item,
                    from_texture = AssetDatabase.LoadAssetAtPath<Texture>(item.from_texture_path),
                    to_texture = AssetDatabase.LoadAssetAtPath<Texture>(item.to_texture_path),
                });
            }
            prepared.texture_events = textureEvents.ToArray();

            var materialEvents = new List<EffectDemoMaterialTrajectoryExecutor.PreparedMaterialEvent>();
            foreach (var item in spec.material_replace_events ?? Array.Empty<EffectDemoMaterialTrajectoryExecutor.MaterialReplaceEvent>())
            {
                materialEvents.Add(new EffectDemoMaterialTrajectoryExecutor.PreparedMaterialEvent
                {
                    definition = item,
                    from_material = AssetDatabase.LoadAssetAtPath<Material>(item.from_material_path),
                    to_material = AssetDatabase.LoadAssetAtPath<Material>(item.to_material_path),
                });
            }
            prepared.material_events = materialEvents.ToArray();
        }
        catch (Exception exception)
        {
            prepared.preparation_error = $"{exception.GetType().Name}: {exception.Message}";
        }
        return prepared;
    }

    private static void ApplyTrackClamps(
        EffectDemoMaterialTrajectoryExecutor.RequestItem request,
        EffectDemoMaterialTrajectoryExecutor.MaterialTrajectorySpec spec)
    {
        var tracks = spec.parameter_tracks ?? Array.Empty<EffectDemoMaterialTrajectoryExecutor.ParameterTrack>();
        var clamps = request.track_clamps ?? Array.Empty<EffectDemoMaterialTrajectoryExecutor.TrackClamp>();
        if (tracks.Length != clamps.Length)
            throw new InvalidOperationException($"Track clamp count mismatch for {request.trajectory_id}: {tracks.Length} != {clamps.Length}");
        for (var index = 0; index < tracks.Length; index++)
        {
            tracks[index].has_clamp_min = clamps[index].has_min;
            tracks[index].clamp_min = clamps[index].min;
            tracks[index].has_clamp_max = clamps[index].has_max;
            tracks[index].clamp_max = clamps[index].max;
        }
    }
}
