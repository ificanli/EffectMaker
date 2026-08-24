using System;
using Unity.Pipeline.Commands;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

public static class VfxPostFxCommands
{
    [CliCommand("verify_postfx", "Read the active URP post-processing configuration")]
    public static object VerifyPostFx()
    {
        var volumeObject = GameObject.Find("Global Volume");
        if (volumeObject == null)
            throw new InvalidOperationException("Global Volume was not found.");

        var volume = volumeObject.GetComponent<Volume>();
        if (volume == null || volume.sharedProfile == null)
            throw new InvalidOperationException("Global Volume has no shared profile.");

        var profile = volume.sharedProfile;
        var hasBloom = profile.TryGet(out Bloom bloom);
        var hasTonemapping = profile.TryGet(out Tonemapping tonemapping);
        var hasMotionBlur = profile.TryGet(out MotionBlur motionBlur);
        var hasVignette = profile.TryGet(out Vignette vignette);

        return new
        {
            profile = AssetDatabasePath(profile),
            volumeGlobal = volume.isGlobal,
            weight = volume.weight,
            bloom = hasBloom ? new { active = bloom.active, intensity = bloom.intensity.value, threshold = bloom.threshold.value } : null,
            tonemapping = hasTonemapping ? new { active = tonemapping.active, mode = tonemapping.mode.value.ToString() } : null,
            motionBlur = hasMotionBlur ? new { active = motionBlur.active } : null,
            vignette = hasVignette ? new { active = vignette.active, intensity = vignette.intensity.value } : null
        };
    }

    private static string AssetDatabasePath(VolumeProfile profile)
    {
        return UnityEditor.AssetDatabase.GetAssetPath(profile);
    }
}
