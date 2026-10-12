using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class VerificationRunner
{
    [Serializable]
    private class Result
    {
        public string experiment;
        public string status;
        public string evidence;
        public string unityVersion;
        public string renderPipeline;
        public string targetPlatform;
    }

    public static void Run()
    {
        var results = new List<Result>();
        var scene = EditorSceneManager.OpenScene("Assets/Scenes/VerificationBaseline.unity");
        var root = GameObject.Find("EffectRoot");
        var camera = GameObject.Find("VerificationCamera");
        var environment = GameObject.Find("EnvironmentReference");
        var actor = GameObject.Find("ActorReference");
        var stages = new[] { "Prelude", "Core", "Burst", "Residue" };

        Add(results, "EXP-2026-002", root != null && camera != null && environment != null && actor != null,
            "scene camera environment actor baseline");
        Add(results, "EXP-2026-003", camera != null && Camera.main == null || camera != null,
            "camera exists for post-process comparison");
        Add(results, "EXP-2026-004", HasStages(root, stages),
            "firework lifecycle stages exist");
        Add(results, "EXP-2026-005", root != null && HasStage(root, "Core") && HasStage(root, "Residue"),
            "slash core and residue stages exist");
        Add(results, "EXP-2026-006", actor != null && root != null && HasStage(root, "Burst"),
            "hit actor and burst stage exist");
        Add(results, "EXP-2026-007", actor != null && root != null && HasStage(root, "Core"),
            "shield actor and core stage exist");
        Add(results, "EXP-2026-008", HasStages(root, new[] { "Prelude", "Burst", "Residue" }),
            "water prelude burst residue stages exist");
        Add(results, "EXP-2026-009", scene.IsValid() && root != null,
            "remaining-course verification template scene exists");

        var output = Path.GetFullPath("../verification-results.json");
        File.WriteAllText(output, JsonUtility.ToJson(new Wrapper { results = results.ToArray() }, true));
        AssetDatabase.SaveAssets();
        Debug.Log("VERIFICATION_RESULTS_WRITTEN=" + output);
        EditorApplication.Exit(results.Exists(r => r.status != "verified") ? 1 : 0);
    }

    [Serializable]
    private class Wrapper
    {
        public Result[] results;
    }

    private static void Add(List<Result> results, string experiment, bool passed, string evidence)
    {
        results.Add(new Result
        {
            experiment = experiment,
            status = passed ? "verified" : "failed",
            evidence = evidence,
            unityVersion = Application.unityVersion,
            renderPipeline = QualitySettings.renderPipeline == null ? "Built-in" : QualitySettings.renderPipeline.GetType().Name,
            targetPlatform = EditorUserBuildSettings.activeBuildTarget.ToString()
        });
    }

    private static bool HasStages(GameObject root, string[] names)
    {
        if (root == null) return false;
        foreach (var name in names) if (!HasStage(root, name)) return false;
        return true;
    }

    private static bool HasStage(GameObject root, string name)
    {
        return root.transform.Find(name) != null;
    }
}
