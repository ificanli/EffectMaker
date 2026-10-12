# Workspace Data

This directory stores generated state and experiment data, not source material.

## Current layout

- `model_index/`: geometry/model indexing outputs and preview data.
- `resource_index/`: resource scan database, thumbnails, and scan summaries.
- `resource_vectors/`: vector search outputs and prototype caches.
- `vfx_generation/`: AI-style VFX generation specs, prompts, runs, feedback, and training dataset indexes.
- `experiments/`: experiment-specific data folders.
- `sword_probe/`: scratch probe data for one-off investigation.

## Guidance

- Treat these folders as rebuildable unless a document explicitly says otherwise.
- Prefer one canonical directory per dataset, with dated subfolders for runs.
- Avoid creating new sibling folders with ad-hoc suffixes like `fix1` unless they are temporary.
