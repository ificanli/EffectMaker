using System;
using System.Linq;
using UnityEngine;

[Serializable]
public sealed class EffectDemoParticleColorGradient
{
    [Serializable] public sealed class ColorKey { public float time; public float[] rgb; }
    [Serializable] public sealed class AlphaKey { public float time; public float alpha; }

    public string mode;
    public ColorKey[] color_keys;
    public AlphaKey[] alpha_keys;

    // JsonUtility constructs an empty object for some absent nested fields.
    public static bool HasData(EffectDemoParticleColorGradient value) => value != null
        && (!string.IsNullOrEmpty(value.mode) || (value.color_keys?.Length ?? 0) > 0 || (value.alpha_keys?.Length ?? 0) > 0);

    public Gradient ToUnity()
    {
        if (mode != "Blend" && mode != "Fixed")
            throw new InvalidOperationException("Particle gradient mode must be Blend or Fixed.");
        if (color_keys == null || color_keys.Length < 2 || color_keys.Length > 8
            || alpha_keys == null || alpha_keys.Length < 2 || alpha_keys.Length > 8)
            throw new InvalidOperationException("Particle gradient requires 2 to 8 color and alpha keys.");
        float previous = -1f;
        foreach (var key in color_keys)
        {
            if (key == null || !Unit(key.time) || key.time <= previous
                || key.rgb == null || key.rgb.Length != 3 || key.rgb.Any(value => !Finite(value) || value < 0f))
                throw new InvalidOperationException("Particle gradient has invalid or unordered color keys.");
            previous = key.time;
        }
        previous = -1f;
        foreach (var key in alpha_keys)
        {
            if (key == null || !Unit(key.time) || key.time <= previous || !Unit(key.alpha))
                throw new InvalidOperationException("Particle gradient has invalid or unordered alpha keys.");
            previous = key.time;
        }
        var gradient = new Gradient { mode = mode == "Fixed" ? GradientMode.Fixed : GradientMode.Blend };
        gradient.SetKeys(
            color_keys.Select(key => new GradientColorKey(new Color(key.rgb[0], key.rgb[1], key.rgb[2], 1f), key.time)).ToArray(),
            alpha_keys.Select(key => new GradientAlphaKey(key.alpha, key.time)).ToArray());
        return gradient;
    }

    public static EffectDemoParticleColorGradient FromUnity(ParticleSystem.MinMaxGradient value)
    {
        Gradient gradient;
        if (value.mode == ParticleSystemGradientMode.Color)
        {
            gradient = new Gradient();
            gradient.SetKeys(new[] { new GradientColorKey(value.color, 0f), new GradientColorKey(value.color, 1f) },
                new[] { new GradientAlphaKey(value.color.a, 0f), new GradientAlphaKey(value.color.a, 1f) });
        }
        else if (value.mode == ParticleSystemGradientMode.Gradient)
            gradient = value.gradient;
        else
            throw new NotSupportedException("Random particle color distribution is not represented: " + value.mode);
        return new EffectDemoParticleColorGradient
        {
            mode = gradient.mode.ToString(),
            color_keys = gradient.colorKeys.Select(key => new ColorKey { time = key.time, rgb = new[] { key.color.r, key.color.g, key.color.b } }).ToArray(),
            alpha_keys = gradient.alphaKeys.Select(key => new AlphaKey { time = key.time, alpha = key.alpha }).ToArray(),
        };
    }

    public static bool Equivalent(EffectDemoParticleColorGradient left, EffectDemoParticleColorGradient right)
    {
        if (left == null || right == null) return left == right;
        if (left.mode != right.mode || left.color_keys.Length != right.color_keys.Length || left.alpha_keys.Length != right.alpha_keys.Length)
            return false;
        for (var index = 0; index < left.color_keys.Length; index++)
        {
            var a = left.color_keys[index];
            var b = right.color_keys[index];
            if (!Close(a.time, b.time) || a.rgb.Length != b.rgb.Length || a.rgb.Where((value, channel) => !Close(value, b.rgb[channel])).Any())
                return false;
        }
        for (var index = 0; index < left.alpha_keys.Length; index++)
            if (!Close(left.alpha_keys[index].time, right.alpha_keys[index].time) || !Close(left.alpha_keys[index].alpha, right.alpha_keys[index].alpha))
                return false;
        return true;
    }

    private static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
    private static bool Unit(float value) => Finite(value) && value >= 0f && value <= 1f;
    private static bool Close(float a, float b) => Finite(a) && Finite(b) && Mathf.Abs(a - b) <= 0.0001f;
}
