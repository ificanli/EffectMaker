using System;
using Unity.Pipeline.Commands;
using UnityEngine;
using UnityEditor.SceneManagement;

public static class VfxFireworksCommands
{
    [CliCommand("build_fireworks", "Build a staged fireworks verification effect")]
    public static object BuildFireworks()
    {
        var root = GameObject.Find("VFX_Verification/EffectRoot");
        if (root == null) throw new InvalidOperationException("EffectRoot was not found.");
        var fireworks = FindOrCreate("Fireworks", root.transform);
        var launch = FindOrCreate("Launch", fireworks.transform);
        var trail = FindOrCreate("AscentTrail", fireworks.transform);
        var core = FindOrCreate("ExplosionCore", fireworks.transform);
        var radial = FindOrCreate("RadialBranches", fireworks.transform);
        var residue = FindOrCreate("Residue", fireworks.transform);

        ConfigureBurst(launch.gameObject, 1.0f, 1, 7f, 0.1f, new Color(1f, 0.8f, 0.2f));
        ConfigureBurst(trail.gameObject, 0.8f, 18, 0.5f, 0.06f, new Color(1f, 0.55f, 0.1f));
        ConfigureBurst(core.gameObject, 0.35f, 10, 1.2f, 0.18f, Color.white);
        ConfigureBurst(radial.gameObject, 1.4f, 48, 3.5f, 0.08f, new Color(1f, 0.35f, 0.05f));
        ConfigureBurst(residue.gameObject, 1.8f, 12, 0.8f, 0.05f, new Color(1f, 0.15f, 0.02f));

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        EditorSceneManager.SaveOpenScenes();
        return new { root = "VFX_Verification/EffectRoot/Fireworks", stages = 5, saved = true };
    }

    private static Transform FindOrCreate(string name, Transform parent)
    {
        var found = parent.Find(name);
        if (found != null) return found;
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        return go.transform;
    }

    private static void ConfigureBurst(GameObject target, float duration, int count, float speed, float size, Color color)
    {
        var ps = target.GetComponent<ParticleSystem>() ?? target.AddComponent<ParticleSystem>();
        var main = ps.main;
        main.loop = false;
        main.playOnAwake = false;
        main.duration = duration;
        main.startLifetime = new ParticleSystem.MinMaxCurve(duration * 0.65f, duration);
        main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.8f, speed);
        main.startSize = new ParticleSystem.MinMaxCurve(size * 0.7f, size);
        main.startColor = new ParticleSystem.MinMaxGradient(color);
        var emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, count) });
        var shape = ps.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.08f;
    }
}
