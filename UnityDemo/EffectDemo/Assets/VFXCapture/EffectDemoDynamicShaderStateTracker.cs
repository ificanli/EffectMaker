using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public static class EffectDemoDynamicShaderStateTracker
{
    [Serializable]
    public sealed class TrackedGlobalValue
    {
        public string property_name;
        public int property_id;
        public string value_kind;
        public float[] numeric_value;
        public string canonical_value;
        public int revision;
        public string writer;
    }

    private sealed class PropertyBlockWrite
    {
        public readonly HashSet<int> PropertyIds = new HashSet<int>();
        public string Writer;
    }

    private static readonly Dictionary<string, string[]> RequiredGlobalsByShader = new Dictionary<string, string[]>(StringComparer.Ordinal)
    {
        { "Hidden/EffectDemo/MaterialStateProbe", new[] { "_EffectDemoTrackedGlobalAlpha" } },
    };

    private static readonly Dictionary<string, TrackedGlobalValue> GlobalValues = new Dictionary<string, TrackedGlobalValue>(StringComparer.Ordinal);
    private static readonly Dictionary<string, PropertyBlockWrite> PropertyBlockWrites = new Dictionary<string, PropertyBlockWrite>(StringComparer.Ordinal);
    private static int globalRevision;

    public static void Reset()
    {
        GlobalValues.Clear();
        PropertyBlockWrites.Clear();
        globalRevision = 0;
    }

    public static void SetGlobalFloat(string propertyName, float value, string writer)
    {
        if (string.IsNullOrWhiteSpace(propertyName))
            throw new ArgumentException("Tracked Shader global property name is required.", nameof(propertyName));
        Shader.SetGlobalFloat(propertyName, value);
        var rounded = (float)Math.Round(Shader.GetGlobalFloat(propertyName), 6, MidpointRounding.AwayFromZero);
        GlobalValues[propertyName] = new TrackedGlobalValue
        {
            property_name = propertyName,
            property_id = Shader.PropertyToID(propertyName),
            value_kind = "float",
            numeric_value = new[] { rounded },
            canonical_value = rounded.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture),
            revision = ++globalRevision,
            writer = string.IsNullOrWhiteSpace(writer) ? "unknown" : writer,
        };
    }

    public static TrackedGlobalValue[] CaptureGlobals(IEnumerable<string> activeShaderNames, out string status)
    {
        var shaders = new HashSet<string>((activeShaderNames ?? Array.Empty<string>()).Where(value => !string.IsNullOrWhiteSpace(value)), StringComparer.Ordinal);
        if (shaders.Count == 0)
        {
            status = "not_instrumented_no_active_shader";
            return Array.Empty<TrackedGlobalValue>();
        }
        foreach (var shaderName in shaders)
        {
            if (!RequiredGlobalsByShader.TryGetValue(shaderName, out var required))
            {
                status = "not_instrumented_unknown_shader";
                return SnapshotGlobals();
            }
            if (required.Any(propertyName => !GlobalValues.ContainsKey(propertyName)))
            {
                status = "not_instrumented_missing_global_write";
                return SnapshotGlobals();
            }
        }
        status = "instrumented";
        return SnapshotGlobals();
    }

    public static void SetPropertyBlock(Renderer renderer, MaterialPropertyBlock block, int materialIndex, string writer, params string[] propertyNames)
    {
        if (renderer == null)
            throw new ArgumentNullException(nameof(renderer));
        if (block == null)
            throw new ArgumentNullException(nameof(block));
        renderer.SetPropertyBlock(block, materialIndex);
        RegisterPropertyBlock(renderer, materialIndex, writer, propertyNames);
        if (materialIndex == 0)
            RegisterPropertyBlock(renderer, -1, writer, propertyNames);
    }

    public static void SetPropertyBlock(Renderer renderer, MaterialPropertyBlock block, string writer, params string[] propertyNames)
    {
        if (renderer == null)
            throw new ArgumentNullException(nameof(renderer));
        if (block == null)
            throw new ArgumentNullException(nameof(block));
        renderer.SetPropertyBlock(block);
        RegisterPropertyBlock(renderer, -1, writer, propertyNames);
    }

    public static bool IsPropertyBlockFullyTracked(Renderer renderer, int materialIndex, MaterialPropertyBlock block, IEnumerable<int> recordedPropertyIds, out int trackedPropertyCount)
    {
        trackedPropertyCount = 0;
        if (block == null || block.isEmpty)
            return true;
        if (renderer == null || !PropertyBlockWrites.TryGetValue(BlockKey(renderer, materialIndex), out var write))
            return false;
        trackedPropertyCount = write.PropertyIds.Count;
        var recorded = new HashSet<int>(recordedPropertyIds ?? Array.Empty<int>());
        return write.PropertyIds.Count > 0 && write.PropertyIds.SetEquals(recorded);
    }

    private static void RegisterPropertyBlock(Renderer renderer, int materialIndex, string writer, IEnumerable<string> propertyNames)
    {
        var write = new PropertyBlockWrite { Writer = string.IsNullOrWhiteSpace(writer) ? "unknown" : writer };
        foreach (var propertyName in propertyNames ?? Array.Empty<string>())
        {
            if (!string.IsNullOrWhiteSpace(propertyName))
                write.PropertyIds.Add(Shader.PropertyToID(propertyName));
        }
        PropertyBlockWrites[BlockKey(renderer, materialIndex)] = write;
    }

    private static string BlockKey(Renderer renderer, int materialIndex) => $"{renderer.GetInstanceID()}:{materialIndex}";

    private static TrackedGlobalValue[] SnapshotGlobals()
    {
        return GlobalValues.Values
            .OrderBy(value => value.property_name, StringComparer.Ordinal)
            .Select(value => new TrackedGlobalValue
            {
                property_name = value.property_name,
                property_id = value.property_id,
                value_kind = value.value_kind,
                numeric_value = value.numeric_value == null ? Array.Empty<float>() : value.numeric_value.ToArray(),
                canonical_value = value.canonical_value,
                revision = value.revision,
                writer = value.writer,
            })
            .ToArray();
    }
}

public interface IEffectDemoCaptureTimingProvider
{
    float CaptureDurationSeconds { get; }
}
