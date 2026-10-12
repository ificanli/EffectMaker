using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.UI;

public sealed class EffectDemoMaterialStateRecorder
{
    [Serializable]
    public sealed class Timeline
    {
        public string schema_version = "vfx_material_timeline.v1";
        public string created_at;
        public string candidate_id;
        public string prefab_path;
        public string capture_mode = "play_mode_runtime";
        public string capture_order = "late_update_barrier -> material_snapshot -> camera_render";
        public string primary_training_signal = "runtime_material_state";
        public string visual_evidence_role = "frame_alignment_only";
        public string source_script_fidelity;
        public int ignored_script_dependency_count;
        public MaterialFrame[] frames;
        public TimelineSummary summary;
        public string[] limitations;
        public string capture_error;
    }

    [Serializable]
    public sealed class TimelineSummary
    {
        public int frame_count;
        public int renderer_count_peak;
        public int material_slot_count_peak;
        public int delta_count;
        public int changed_frame_count;
        public bool has_dynamic_material_state;
        public bool has_unenumerated_property_block_values;
        public string global_shader_state_status;
        public int global_shader_value_count;
        public int global_shader_delta_count;
        public float[] key_material_change_times;
        public SignalCount[] signal_counts;
    }

    [Serializable]
    public sealed class SignalCount
    {
        public string signal;
        public int count;
    }

    [Serializable]
    public sealed class MaterialFrame
    {
        public int frame_index;
        public int unity_frame_count;
        public float requested_time_seconds;
        public float capture_time_seconds;
        public string image_path;
        public RendererState[] renderers;
        public EffectDemoDynamicShaderStateTracker.TrackedGlobalValue[] global_shader_values;
        public string global_shader_state_status;
        public MaterialDelta[] deltas_from_previous;
    }

    [Serializable]
    public sealed class RendererState
    {
        public string hierarchy_path;
        public string renderer_type;
        public int renderer_instance_id;
        public bool enabled;
        public bool active_in_hierarchy;
        public MaterialSlotState[] material_slots;
    }

    [Serializable]
    public sealed class MaterialSlotState
    {
        public int slot_index;
        public bool material_missing;
        public int material_instance_id;
        public string material_name;
        public string material_asset_path;
        public string shader_name;
        public string shader_asset_path;
        public int render_queue;
        public string[] shader_keywords;
        public PropertyState[] material_properties;
        public PropertyBlockState renderer_property_block;
        public PropertyBlockState slot_property_block;
        public string active_property_block_scope;
    }

    [Serializable]
    public sealed class PropertyBlockState
    {
        public bool is_empty;
        public bool has_unenumerated_values;
        public PropertyState[] properties;
    }

    [Serializable]
    public sealed class PropertyState
    {
        public string property_name;
        public int property_id;
        public string display_name;
        public string property_type;
        public string[] flags;
        public string[] semantic_tags;
        public string source;
        public string value_kind;
        public float[] numeric_value;
        public TextureState texture_value;
        public float[] texture_scale;
        public float[] texture_offset;
        public string canonical_value;
    }

    [Serializable]
    public sealed class TextureState
    {
        public int instance_id;
        public string name;
        public string asset_path;
        public int width;
        public int height;
        public string dimension;
        public bool runtime_generated;
    }

    [Serializable]
    public sealed class MaterialDelta
    {
        public string[] categories;
        public string renderer_path;
        public int material_slot;
        public string property_name;
        public string[] semantic_tags;
        public string before_value;
        public string after_value;
    }

    private sealed class PropertyDescriptor
    {
        public string Name;
        public int Id;
        public string DisplayName;
        public ShaderPropertyType Type;
        public string[] Flags;
        public string[] SemanticTags;
    }

    private static readonly (string Name, ShaderPropertyType Type)[] KnownAliases =
    {
        ("_Dissolve", ShaderPropertyType.Float),
        ("_DissolveAmount", ShaderPropertyType.Float),
        ("_DissolveValue", ShaderPropertyType.Float),
        ("_DissolveProgress", ShaderPropertyType.Float),
        ("_DissolveThreshold", ShaderPropertyType.Float),
        ("_BurnAmount", ShaderPropertyType.Float),
        ("_Cutoff", ShaderPropertyType.Float),
        ("_Threshold", ShaderPropertyType.Float),
        ("_Fade", ShaderPropertyType.Float),
        ("_FadeAmount", ShaderPropertyType.Float),
        ("_Alpha", ShaderPropertyType.Float),
        ("_Opacity", ShaderPropertyType.Float),
        ("_FlowSpeed", ShaderPropertyType.Float),
        ("_Distortion", ShaderPropertyType.Float),
        ("_DistortionStrength", ShaderPropertyType.Float),
        ("_EmissionIntensity", ShaderPropertyType.Float),
        ("_DissolveTex", ShaderPropertyType.Texture),
        ("_DissolveMap", ShaderPropertyType.Texture),
        ("_MaskTex", ShaderPropertyType.Texture),
        ("_MaskMap", ShaderPropertyType.Texture),
        ("_FlowTex", ShaderPropertyType.Texture),
        ("_FlowMap", ShaderPropertyType.Texture),
        ("_NoiseTex", ShaderPropertyType.Texture),
        ("_NoiseMap", ShaderPropertyType.Texture),
        ("_DistortionTex", ShaderPropertyType.Texture),
        ("_EmissionMap", ShaderPropertyType.Texture),
        ("_DissolveColor", ShaderPropertyType.Color),
        ("_EdgeColor", ShaderPropertyType.Color),
        ("_EmissionColor", ShaderPropertyType.Color),
        ("_FlowDirection", ShaderPropertyType.Vector),
    };

    private readonly List<MaterialFrame> frames = new List<MaterialFrame>();
    private readonly List<string> globalStatuses = new List<string>();

    public Timeline CreateTimeline(EffectDemoRuntimeCaptureController.RequestItem request)
    {
        return new Timeline
        {
            created_at = DateTime.UtcNow.ToString("o"),
            candidate_id = request.candidate_id,
            prefab_path = request.prefab_path,
            source_script_fidelity = string.IsNullOrWhiteSpace(request.source_script_fidelity) ? "unknown" : request.source_script_fidelity,
            ignored_script_dependency_count = request.ignored_script_dependency_count,
            frames = Array.Empty<MaterialFrame>(),
            summary = new TimelineSummary
            {
                signal_counts = Array.Empty<SignalCount>(),
                key_material_change_times = Array.Empty<float>(),
                global_shader_state_status = "not_instrumented",
            },
            limitations = BuildLimitations(request),
        };
    }

    public MaterialFrame CaptureFrame(GameObject root, int frameIndex, float requestedTime, float captureTime, string imagePath)
    {
        var renderers = root.GetComponentsInChildren<Renderer>(true)
            .Select(renderer => CaptureRenderer(root.transform, renderer))
            .Concat(root.GetComponentsInChildren<Graphic>(true).Select(graphic => CaptureGraphic(root.transform, graphic)))
            .OrderBy(renderer => renderer.hierarchy_path, StringComparer.Ordinal)
            .ToArray();
        var activeShaderNames = renderers
            .SelectMany(renderer => renderer.material_slots ?? Array.Empty<MaterialSlotState>())
            .Where(slot => !slot.material_missing && !string.IsNullOrWhiteSpace(slot.shader_name))
            .Select(slot => slot.shader_name)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        var globalValues = EffectDemoDynamicShaderStateTracker.CaptureGlobals(activeShaderNames, out var globalStatus);
        var frame = new MaterialFrame
        {
            frame_index = frameIndex,
            unity_frame_count = Time.frameCount,
            requested_time_seconds = requestedTime,
            capture_time_seconds = captureTime,
            image_path = imagePath,
            renderers = renderers,
            global_shader_values = globalValues,
            global_shader_state_status = globalStatus,
            deltas_from_previous = frames.Count == 0 ? Array.Empty<MaterialDelta>() : CompareFrames(frames[frames.Count - 1], renderers, globalValues),
        };
        frames.Add(frame);
        globalStatuses.Add(globalStatus);
        return frame;
    }

    public void Complete(Timeline timeline, string error = null)
    {
        timeline.capture_error = error;
        timeline.frames = frames.ToArray();
        var allDeltas = frames.SelectMany(frame => frame.deltas_from_previous ?? Array.Empty<MaterialDelta>()).ToArray();
        var hasUnenumeratedPropertyBlockValues = frames
            .SelectMany(frame => frame.renderers ?? Array.Empty<RendererState>())
            .SelectMany(renderer => renderer.material_slots ?? Array.Empty<MaterialSlotState>())
            .Any(slot => (slot.renderer_property_block?.has_unenumerated_values ?? false)
                || (slot.slot_property_block?.has_unenumerated_values ?? false));
        var globalDeltas = allDeltas.Count(delta => (delta.categories ?? Array.Empty<string>()).Contains("shader_global_changed"));
        var globalStatus = globalStatuses.Count > 0 && globalStatuses.All(value => string.Equals(value, "instrumented", StringComparison.Ordinal))
            ? "instrumented"
            : globalStatuses.LastOrDefault(value => !string.Equals(value, "instrumented", StringComparison.Ordinal)) ?? "not_instrumented";
        var signals = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var category in allDeltas.SelectMany(delta => delta.categories ?? Array.Empty<string>()))
            signals[category] = signals.TryGetValue(category, out var count) ? count + 1 : 1;
        timeline.summary = new TimelineSummary
        {
            frame_count = frames.Count,
            renderer_count_peak = frames.Count == 0 ? 0 : frames.Max(frame => frame.renderers?.Length ?? 0),
            material_slot_count_peak = frames.Count == 0 ? 0 : frames.Max(frame => (frame.renderers ?? Array.Empty<RendererState>()).Sum(renderer => renderer.material_slots?.Length ?? 0)),
            delta_count = allDeltas.Length,
            changed_frame_count = frames.Count(frame => (frame.deltas_from_previous?.Length ?? 0) > 0),
            has_dynamic_material_state = allDeltas.Length > 0,
            has_unenumerated_property_block_values = hasUnenumeratedPropertyBlockValues,
            global_shader_state_status = globalStatus,
            global_shader_value_count = frames.SelectMany(frame => frame.global_shader_values ?? Array.Empty<EffectDemoDynamicShaderStateTracker.TrackedGlobalValue>()).Select(value => value.property_name).Distinct(StringComparer.Ordinal).Count(),
            global_shader_delta_count = globalDeltas,
            key_material_change_times = frames.Where(frame => (frame.deltas_from_previous?.Length ?? 0) > 0).Select(frame => (float)Math.Round(frame.capture_time_seconds, 4)).Distinct().ToArray(),
            signal_counts = signals.OrderBy(item => item.Key, StringComparer.Ordinal).Select(item => new SignalCount { signal = item.Key, count = item.Value }).ToArray(),
        };
    }

    private static RendererState CaptureRenderer(Transform root, Renderer renderer)
    {
        var rendererBlock = new MaterialPropertyBlock();
        renderer.GetPropertyBlock(rendererBlock);
        var materials = renderer.sharedMaterials;
        var slots = new List<MaterialSlotState>();
        for (var slot = 0; slot < materials.Length; slot++)
        {
            var material = materials[slot];
            if (material == null || material.shader == null)
            {
                slots.Add(new MaterialSlotState { slot_index = slot, material_missing = true, shader_keywords = Array.Empty<string>(), material_properties = Array.Empty<PropertyState>() });
                continue;
            }
            var slotBlock = new MaterialPropertyBlock();
            renderer.GetPropertyBlock(slotBlock, slot);
            var descriptors = BuildDescriptors(material.shader, material, rendererBlock, slotBlock);
            var keywords = material.shaderKeywords ?? Array.Empty<string>();
            Array.Sort(keywords, StringComparer.Ordinal);
            slots.Add(new MaterialSlotState
            {
                slot_index = slot,
                material_instance_id = material.GetInstanceID(),
                material_name = material.name,
                material_asset_path = AssetPath(material),
                shader_name = material.shader.name,
                shader_asset_path = AssetPath(material.shader),
                render_queue = material.renderQueue,
                shader_keywords = keywords,
                material_properties = descriptors.Where(descriptor => material.HasProperty(descriptor.Id)).Select(descriptor => ReadMaterialProperty(material, descriptor)).ToArray(),
                renderer_property_block = ReadPropertyBlock(renderer, -1, rendererBlock, descriptors, "renderer_property_block"),
                slot_property_block = ReadPropertyBlock(renderer, slot, slotBlock, descriptors, "slot_property_block"),
                active_property_block_scope = !slotBlock.isEmpty ? "slot" : !rendererBlock.isEmpty ? "renderer" : "material",
            });
        }
        return new RendererState
        {
            hierarchy_path = HierarchyPath(root, renderer.transform),
            renderer_type = renderer.GetType().Name,
            renderer_instance_id = renderer.GetInstanceID(),
            enabled = renderer.enabled,
            active_in_hierarchy = renderer.gameObject.activeInHierarchy,
            material_slots = slots.ToArray(),
        };
    }

    private static RendererState CaptureGraphic(Transform root, Graphic graphic)
    {
        var material = graphic.material;
        var slots = new List<MaterialSlotState>();
        if (material == null || material.shader == null)
        {
            slots.Add(new MaterialSlotState
            {
                slot_index = 0,
                material_missing = true,
                shader_keywords = Array.Empty<string>(),
                material_properties = Array.Empty<PropertyState>(),
                renderer_property_block = new PropertyBlockState { is_empty = true, properties = Array.Empty<PropertyState>() },
                slot_property_block = new PropertyBlockState { is_empty = true, properties = Array.Empty<PropertyState>() },
                active_property_block_scope = "material",
            });
        }
        else
        {
            var emptyRendererBlock = new MaterialPropertyBlock();
            var emptySlotBlock = new MaterialPropertyBlock();
            var descriptors = BuildDescriptors(material.shader, material, emptyRendererBlock, emptySlotBlock);
            var keywords = material.shaderKeywords ?? Array.Empty<string>();
            Array.Sort(keywords, StringComparer.Ordinal);
            slots.Add(new MaterialSlotState
            {
                slot_index = 0,
                material_instance_id = material.GetInstanceID(),
                material_name = material.name,
                material_asset_path = AssetPath(material),
                shader_name = material.shader.name,
                shader_asset_path = AssetPath(material.shader),
                render_queue = material.renderQueue,
                shader_keywords = keywords,
                material_properties = descriptors.Where(descriptor => material.HasProperty(descriptor.Id)).Select(descriptor => ReadMaterialProperty(material, descriptor)).ToArray(),
                renderer_property_block = ReadPropertyBlock(null, -1, emptyRendererBlock, descriptors, "renderer_property_block"),
                slot_property_block = ReadPropertyBlock(null, 0, emptySlotBlock, descriptors, "slot_property_block"),
                active_property_block_scope = "material",
            });
        }
        return new RendererState
        {
            hierarchy_path = HierarchyPath(root, graphic.transform),
            renderer_type = graphic.GetType().Name,
            renderer_instance_id = graphic.GetInstanceID(),
            enabled = graphic.enabled,
            active_in_hierarchy = graphic.gameObject.activeInHierarchy,
            material_slots = slots.ToArray(),
        };
    }

    private static List<PropertyDescriptor> BuildDescriptors(Shader shader, Material material, MaterialPropertyBlock rendererBlock, MaterialPropertyBlock slotBlock)
    {
        var result = new List<PropertyDescriptor>();
        var names = new HashSet<string>(StringComparer.Ordinal);
        for (var index = 0; index < shader.GetPropertyCount(); index++)
        {
            var name = shader.GetPropertyName(index);
            if (!names.Add(name))
                continue;
            result.Add(new PropertyDescriptor
            {
                Name = name,
                Id = shader.GetPropertyNameId(index),
                DisplayName = shader.GetPropertyDescription(index),
                Type = shader.GetPropertyType(index),
                Flags = EnumFlags(shader.GetPropertyFlags(index)),
                SemanticTags = SemanticTags(name, shader.GetPropertyDescription(index), shader.GetPropertyType(index)),
            });
        }
        foreach (var alias in KnownAliases)
        {
            if (names.Contains(alias.Name))
                continue;
            var id = Shader.PropertyToID(alias.Name);
            if (!material.HasProperty(id) && !rendererBlock.HasProperty(id) && !slotBlock.HasProperty(id))
                continue;
            result.Add(new PropertyDescriptor
            {
                Name = alias.Name,
                Id = id,
                DisplayName = alias.Name,
                Type = alias.Type,
                Flags = new[] { "known_vfx_alias" },
                SemanticTags = SemanticTags(alias.Name, alias.Name, alias.Type),
            });
        }
        return result;
    }

    private static PropertyState ReadMaterialProperty(Material material, PropertyDescriptor descriptor)
    {
        var state = BaseProperty(descriptor, "material");
        switch (descriptor.Type)
        {
            case ShaderPropertyType.Color:
                SetNumeric(state, "color", material.GetColor(descriptor.Id));
                break;
            case ShaderPropertyType.Vector:
                SetNumeric(state, "vector", material.GetVector(descriptor.Id));
                break;
            case ShaderPropertyType.Float:
            case ShaderPropertyType.Range:
                SetNumeric(state, "float", material.GetFloat(descriptor.Id));
                break;
            case ShaderPropertyType.Int:
                SetNumeric(state, "int", material.GetInteger(descriptor.Id));
                break;
            case ShaderPropertyType.Texture:
                SetTexture(state, material.GetTexture(descriptor.Id));
                var scale = material.GetTextureScale(descriptor.Id);
                var offset = material.GetTextureOffset(descriptor.Id);
                state.texture_scale = Values(scale.x, scale.y);
                state.texture_offset = Values(offset.x, offset.y);
                state.canonical_value += $"|scale={Canonical(scale.x)},{Canonical(scale.y)}|offset={Canonical(offset.x)},{Canonical(offset.y)}";
                break;
        }
        return state;
    }

    private static PropertyBlockState ReadPropertyBlock(Renderer renderer, int materialIndex, MaterialPropertyBlock block, List<PropertyDescriptor> descriptors, string source)
    {
        var properties = descriptors.Where(descriptor => block.HasProperty(descriptor.Id)).Select(descriptor => ReadBlockProperty(block, descriptor, source)).ToArray();
        var tracked = EffectDemoDynamicShaderStateTracker.IsPropertyBlockFullyTracked(renderer, materialIndex, block, properties.Select(property => property.property_id), out _);
        return new PropertyBlockState
        {
            is_empty = block.isEmpty,
            has_unenumerated_values = !block.isEmpty && (!tracked || properties.Length == 0),
            properties = properties,
        };
    }

    private static PropertyState ReadBlockProperty(MaterialPropertyBlock block, PropertyDescriptor descriptor, string source)
    {
        var state = BaseProperty(descriptor, source);
        if (block.HasTexture(descriptor.Id))
            SetTexture(state, block.GetTexture(descriptor.Id));
        else if (block.HasColor(descriptor.Id) || descriptor.Type == ShaderPropertyType.Color)
            SetNumeric(state, "color", block.GetColor(descriptor.Id));
        else if (block.HasVector(descriptor.Id) || descriptor.Type == ShaderPropertyType.Vector)
            SetNumeric(state, "vector", block.GetVector(descriptor.Id));
        else if (block.HasInteger(descriptor.Id) || descriptor.Type == ShaderPropertyType.Int)
            SetNumeric(state, "int", block.GetInteger(descriptor.Id));
        else
            SetNumeric(state, "float", block.GetFloat(descriptor.Id));
        return state;
    }

    private static PropertyState BaseProperty(PropertyDescriptor descriptor, string source)
    {
        return new PropertyState
        {
            property_name = descriptor.Name,
            property_id = descriptor.Id,
            display_name = descriptor.DisplayName,
            property_type = descriptor.Type.ToString().ToLowerInvariant(),
            flags = descriptor.Flags,
            semantic_tags = descriptor.SemanticTags,
            source = source,
        };
    }

    private static void SetNumeric(PropertyState state, string kind, float value) => SetNumeric(state, kind, new Vector4(value, 0f, 0f, 0f), 1);
    private static void SetNumeric(PropertyState state, string kind, int value) => SetNumeric(state, kind, new Vector4(value, 0f, 0f, 0f), 1);
    private static void SetNumeric(PropertyState state, string kind, Color value) => SetNumeric(state, kind, new Vector4(value.r, value.g, value.b, value.a), 4);
    private static void SetNumeric(PropertyState state, string kind, Vector4 value) => SetNumeric(state, kind, value, 4);

    private static void SetNumeric(PropertyState state, string kind, Vector4 value, int count)
    {
        state.value_kind = kind;
        state.numeric_value = count == 1 ? Values(value.x) : Values(value.x, value.y, value.z, value.w);
        state.canonical_value = string.Join(",", state.numeric_value.Select(Canonical));
    }

    private static void SetTexture(PropertyState state, Texture texture)
    {
        state.value_kind = "texture";
        state.texture_value = texture == null ? null : new TextureState
        {
            instance_id = texture.GetInstanceID(),
            name = texture.name,
            asset_path = AssetPath(texture),
            width = texture.width,
            height = texture.height,
            dimension = texture.dimension.ToString(),
            runtime_generated = string.IsNullOrWhiteSpace(AssetPath(texture)),
        };
        state.canonical_value = texture == null ? "null" : $"id={texture.GetInstanceID()}|path={AssetPath(texture)}|name={texture.name}";
    }

    private static MaterialDelta[] CompareFrames(MaterialFrame previous, RendererState[] currentRenderers, EffectDemoDynamicShaderStateTracker.TrackedGlobalValue[] currentGlobals)
    {
        var deltas = new List<MaterialDelta>();
        var previousRenderers = (previous.renderers ?? Array.Empty<RendererState>()).ToDictionary(item => item.hierarchy_path, StringComparer.Ordinal);
        var current = currentRenderers.ToDictionary(item => item.hierarchy_path, StringComparer.Ordinal);
        foreach (var path in previousRenderers.Keys.Except(current.Keys))
            deltas.Add(Delta(new[] { "renderer_removed" }, path, -1, null, null, "present", "missing"));
        foreach (var path in current.Keys.Except(previousRenderers.Keys))
            deltas.Add(Delta(new[] { "renderer_added" }, path, -1, null, null, "missing", "present"));
        foreach (var path in current.Keys.Intersect(previousRenderers.Keys))
            CompareRenderer(previousRenderers[path], current[path], deltas);
        CompareGlobals(previous.global_shader_values, currentGlobals, deltas);
        return deltas.ToArray();
    }

    private static void CompareGlobals(EffectDemoDynamicShaderStateTracker.TrackedGlobalValue[] previous, EffectDemoDynamicShaderStateTracker.TrackedGlobalValue[] current, List<MaterialDelta> deltas)
    {
        var before = (previous ?? Array.Empty<EffectDemoDynamicShaderStateTracker.TrackedGlobalValue>()).ToDictionary(value => value.property_name, StringComparer.Ordinal);
        var after = (current ?? Array.Empty<EffectDemoDynamicShaderStateTracker.TrackedGlobalValue>()).ToDictionary(value => value.property_name, StringComparer.Ordinal);
        foreach (var name in before.Keys.Union(after.Keys))
        {
            before.TryGetValue(name, out var left);
            after.TryGetValue(name, out var right);
            var leftValue = left?.canonical_value ?? "missing";
            var rightValue = right?.canonical_value ?? "missing";
            if (!string.Equals(leftValue, rightValue, StringComparison.Ordinal))
                deltas.Add(Delta(new[] { "shader_global_changed" }, "<shader_global>", -1, name, SemanticTags(name, name, ShaderPropertyType.Float), leftValue, rightValue));
        }
    }

    private static void CompareRenderer(RendererState previous, RendererState current, List<MaterialDelta> deltas)
    {
        var previousSlots = (previous.material_slots ?? Array.Empty<MaterialSlotState>()).ToDictionary(slot => slot.slot_index);
        var currentSlots = (current.material_slots ?? Array.Empty<MaterialSlotState>()).ToDictionary(slot => slot.slot_index);
        foreach (var index in previousSlots.Keys.Except(currentSlots.Keys))
            deltas.Add(Delta(new[] { "material_slot_removed" }, current.hierarchy_path, index, null, null, "present", "missing"));
        foreach (var index in currentSlots.Keys.Except(previousSlots.Keys))
            deltas.Add(Delta(new[] { "material_slot_added" }, current.hierarchy_path, index, null, null, "missing", "present"));
        foreach (var index in currentSlots.Keys.Intersect(previousSlots.Keys))
            CompareSlot(current.hierarchy_path, previousSlots[index], currentSlots[index], deltas);
    }

    private static void CompareSlot(string path, MaterialSlotState previous, MaterialSlotState current, List<MaterialDelta> deltas)
    {
        if (previous.material_instance_id != current.material_instance_id)
            deltas.Add(Delta(new[] { "material_instance_replaced" }, path, current.slot_index, null, null, previous.material_instance_id.ToString(), current.material_instance_id.ToString()));
        if (!string.Equals(previous.shader_name, current.shader_name, StringComparison.Ordinal))
            deltas.Add(Delta(new[] { "shader_changed" }, path, current.slot_index, null, null, previous.shader_name, current.shader_name));
        if (previous.render_queue != current.render_queue)
            deltas.Add(Delta(new[] { "render_queue_changed" }, path, current.slot_index, null, null, previous.render_queue.ToString(), current.render_queue.ToString()));
        var beforeKeywords = string.Join("|", previous.shader_keywords ?? Array.Empty<string>());
        var afterKeywords = string.Join("|", current.shader_keywords ?? Array.Empty<string>());
        if (!string.Equals(beforeKeywords, afterKeywords, StringComparison.Ordinal))
            deltas.Add(Delta(new[] { "shader_keywords_changed" }, path, current.slot_index, null, null, beforeKeywords, afterKeywords));
        CompareProperties(path, current.slot_index, previous.material_properties, current.material_properties, "material_property_changed", deltas);
        CompareProperties(path, current.slot_index, previous.renderer_property_block?.properties, current.renderer_property_block?.properties, "renderer_property_block_changed", deltas);
        CompareProperties(path, current.slot_index, previous.slot_property_block?.properties, current.slot_property_block?.properties, "slot_property_block_changed", deltas);
    }

    private static void CompareProperties(string path, int slot, PropertyState[] previous, PropertyState[] current, string baseCategory, List<MaterialDelta> deltas)
    {
        var before = LastPropertyByName(previous);
        var after = LastPropertyByName(current);
        foreach (var name in before.Keys.Union(after.Keys))
        {
            before.TryGetValue(name, out var left);
            after.TryGetValue(name, out var right);
            var leftValue = left?.canonical_value ?? "missing";
            var rightValue = right?.canonical_value ?? "missing";
            if (string.Equals(leftValue, rightValue, StringComparison.Ordinal))
                continue;
            var tags = (right?.semantic_tags ?? left?.semantic_tags ?? Array.Empty<string>()).Distinct().ToArray();
            var categories = new List<string> { baseCategory };
            if ((right?.value_kind ?? left?.value_kind) == "texture")
                categories.Add("texture_changed");
            if (tags.Contains("dissolve"))
                categories.Add("dissolve_parameter_changed");
            deltas.Add(Delta(categories.ToArray(), path, slot, name, tags, leftValue, rightValue));
        }
    }

    private static Dictionary<string, PropertyState> LastPropertyByName(PropertyState[] values)
    {
        return (values ?? Array.Empty<PropertyState>())
            .Where(item => item != null && !string.IsNullOrWhiteSpace(item.property_name))
            .GroupBy(item => item.property_name, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Last(), StringComparer.Ordinal);
    }

    private static MaterialDelta Delta(string[] categories, string path, int slot, string property, string[] tags, string before, string after)
    {
        return new MaterialDelta { categories = categories, renderer_path = path, material_slot = slot, property_name = property, semantic_tags = tags ?? Array.Empty<string>(), before_value = before, after_value = after };
    }

    private static string HierarchyPath(Transform root, Transform target)
    {
        var segments = new List<string>();
        var current = target;
        while (current != null)
        {
            segments.Add($"{current.name}[{current.GetSiblingIndex()}]");
            if (current == root)
                break;
            current = current.parent;
        }
        segments.Reverse();
        return string.Join("/", segments);
    }

    private static string[] SemanticTags(string name, string description, ShaderPropertyType type)
    {
        var text = ((name ?? string.Empty) + " " + (description ?? string.Empty)).ToLowerInvariant();
        var tags = new List<string>();
        if (type == ShaderPropertyType.Texture) tags.Add("texture");
        if (ContainsAny(text, "dissolv", "burn", "erosion", "cutoff", "clip", "threshold")) tags.Add("dissolve");
        if (ContainsAny(text, "mask", "stencil")) tags.Add("mask");
        if (ContainsAny(text, "flow", "scroll", "pan", "uvspeed")) tags.Add("flow");
        if (ContainsAny(text, "distort", "warp", "refraction")) tags.Add("distortion");
        if (ContainsAny(text, "emission", "glow")) tags.Add("emission");
        if (ContainsAny(text, "alpha", "opacity", "fade")) tags.Add("alpha");
        if (ContainsAny(text, "noise")) tags.Add("noise");
        return tags.Distinct().ToArray();
    }

    private static bool ContainsAny(string text, params string[] values) => values.Any(text.Contains);
    private static string[] EnumFlags(ShaderPropertyFlags flags) => Enum.GetValues(typeof(ShaderPropertyFlags)).Cast<ShaderPropertyFlags>().Where(value => value != ShaderPropertyFlags.None && flags.HasFlag(value)).Select(value => value.ToString()).ToArray();
    private static float[] Values(params float[] values) => values.Select(value => (float)Math.Round(value, 6, MidpointRounding.AwayFromZero)).ToArray();
    private static string Canonical(float value) => value.ToString("0.######", CultureInfo.InvariantCulture);

    private static string AssetPath(UnityEngine.Object value)
    {
#if UNITY_EDITOR
        return UnityEditor.AssetDatabase.GetAssetPath(value) ?? string.Empty;
#else
        return string.Empty;
#endif
    }

    private static string[] BuildLimitations(EffectDemoRuntimeCaptureController.RequestItem request)
    {
        var result = new List<string>
        {
            "MaterialPropertyBlock does not expose unknown property IDs; Shader-declared properties and known VFX aliases are queried.",
            "Only explicitly tracked Shader global writes and registered MaterialPropertyBlock property IDs are complete; unknown state remains a limitation.",
        };
        if (request.ignored_script_dependency_count > 0)
            result.Add("The imported Prefab excluded source runtime scripts; this timeline is incomplete until the material-driver scripts run in source or isolated context.");
        return result.ToArray();
    }
}
