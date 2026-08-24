using System;
using Unity.Pipeline.Commands;
using UnityEngine;
using UnityEditor.SceneManagement;

public static class VfxVerificationCommands
{
    [CliCommand("configure_burst", "Configure the verification burst particle system")]
    public static object ConfigureBurst()
    {
        var burst = GameObject.Find("VFX_Verification/EffectRoot/Burst");
        if (burst == null)
            throw new InvalidOperationException("VFX_Verification/EffectRoot/Burst was not found.");

        var particles = burst.GetComponent<ParticleSystem>() ?? burst.AddComponent<ParticleSystem>();
        var main = particles.main;
        main.loop = false;
        main.playOnAwake = false;
        main.duration = 1.2f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.2f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(2.5f, 4f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.08f, 0.18f);
        main.startColor = new ParticleSystem.MinMaxGradient(new Color(1f, 0.45f, 0.08f, 1f));

        var emission = particles.emission;
        emission.enabled = true;
        emission.rateOverTime = 0f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 32) });

        var shape = particles.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.15f;

        var renderer = particles.GetComponent<ParticleSystemRenderer>();
        renderer.renderMode = ParticleSystemRenderMode.Billboard;

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        EditorSceneManager.SaveOpenScenes();
        return new { objectPath = burst.name, duration = main.duration, burstCount = 32, saved = true };
    }
}
