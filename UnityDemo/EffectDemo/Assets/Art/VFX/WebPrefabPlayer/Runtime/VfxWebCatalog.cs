using System;
using System.Collections.Generic;
using UnityEngine;

namespace VfxPrefabWeb
{
    [CreateAssetMenu(fileName = "VfxWebCatalog", menuName = "VFX/Web Prefab Catalog")]
    public sealed class VfxWebCatalog : ScriptableObject
    {
        [Serializable]
        public sealed class Entry
        {
            [SerializeField] private string id;
            [SerializeField] private string displayName;
            [SerializeField] private string category;
            [SerializeField] private string assetPath;
            [SerializeField] private string sourcePath;
            [SerializeField] private string playability;
            [SerializeField] private GameObject prefab;
            [SerializeField] private int particleSystemCount;
            [SerializeField] private int rendererCount;
            [SerializeField] private float suggestedDuration;
            [SerializeField] private string runId;
            [SerializeField] private string candidateId;
            [SerializeField] private string trainingCaseId;
            [SerializeField] private string effectFamily;
            [SerializeField] private string materialTimelinePath;
            [SerializeField] private string materialTimelineStatus;
            [SerializeField] private int materialChangeCount;
            [SerializeField] private float[] materialKeyTimes;
            [SerializeField] private string sourceScriptFidelity;
            [SerializeField] private string specPath;
            [SerializeField] private string renderManifestPath;
            [SerializeField] private bool hasSeed;
            [SerializeField] private int seed;
            [SerializeField] private string generator;
            [SerializeField] private string generatorVersion;

            public string Id => id;
            public string DisplayName => displayName;
            public string Category => category;
            public string AssetPath => assetPath;
            public string SourcePath => sourcePath;
            public string Playability => playability;
            public GameObject Prefab => prefab;
            public int ParticleSystemCount => particleSystemCount;
            public int RendererCount => rendererCount;
            public float SuggestedDuration => suggestedDuration;
            public string RunId => runId;
            public string CandidateId => candidateId;
            public string TrainingCaseId => trainingCaseId;
            public string EffectFamily => effectFamily;
            public string MaterialTimelinePath => materialTimelinePath;
            public string MaterialTimelineStatus => materialTimelineStatus;
            public int MaterialChangeCount => materialChangeCount;
            public float[] MaterialKeyTimes => materialKeyTimes ?? Array.Empty<float>();
            public string SourceScriptFidelity => sourceScriptFidelity;
            public string SpecPath => specPath;
            public string RenderManifestPath => renderManifestPath;
            public bool HasSeed => hasSeed;
            public int Seed => seed;
            public string Generator => generator;
            public string GeneratorVersion => generatorVersion;

#if UNITY_EDITOR
            public Entry(
                string id,
                string displayName,
                string category,
                string assetPath,
                string sourcePath,
                string playability,
                GameObject prefab,
                int particleSystemCount,
                int rendererCount,
                float suggestedDuration,
                string runId,
                string candidateId,
                string trainingCaseId,
                string effectFamily,
                string materialTimelinePath,
                string materialTimelineStatus,
                int materialChangeCount,
                float[] materialKeyTimes,
                string sourceScriptFidelity,
                string specPath,
                string renderManifestPath,
                bool hasSeed,
                int seed,
                string generator,
                string generatorVersion)
            {
                this.id = id;
                this.displayName = displayName;
                this.category = category;
                this.assetPath = assetPath;
                this.sourcePath = sourcePath;
                this.playability = playability;
                this.prefab = prefab;
                this.particleSystemCount = particleSystemCount;
                this.rendererCount = rendererCount;
                this.suggestedDuration = suggestedDuration;
                this.runId = runId;
                this.candidateId = candidateId;
                this.trainingCaseId = trainingCaseId;
                this.effectFamily = effectFamily;
                this.materialTimelinePath = materialTimelinePath;
                this.materialTimelineStatus = materialTimelineStatus;
                this.materialChangeCount = materialChangeCount;
                this.materialKeyTimes = materialKeyTimes ?? Array.Empty<float>();
                this.sourceScriptFidelity = sourceScriptFidelity;
                this.specPath = specPath;
                this.renderManifestPath = renderManifestPath;
                this.hasSeed = hasSeed;
                this.seed = seed;
                this.generator = generator;
                this.generatorVersion = generatorVersion;
            }
#endif
        }

        [SerializeField] private List<Entry> entries = new List<Entry>();

        public IReadOnlyList<Entry> Entries => entries;

#if UNITY_EDITOR
        public void ReplaceEntries(IEnumerable<Entry> replacement)
        {
            entries.Clear();
            entries.AddRange(replacement);
        }
#endif
    }
}
