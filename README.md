# Public repository upload rules

This repository contains the reproducible parts of a Unity VFX and AI-assisted learning workspace:

- `UnityDemo/`: Unity project source and project settings that are suitable for version control.
- `workspace/`: media utilities, indexing code, tests, and verification notes.
- `knowledge/`: source records, links, transcripts, visual review notes, cards, and experiments.
- `docs/`: operating procedures and project documentation.

## Media and asset boundary

Video and audio files are intentionally not committed. The local workspace may contain downloaded copies under `knowledge/sources/**/videos/` and derived audio under `audio/` or `audio_segments/`; these paths are ignored by Git. Source records retain the original public reference, usually a Bilibili space or BV page, so the material can be located without redistributing the downloaded file.

The repository also excludes local Unity caches, generated editor indexes, model/RAG caches, archives, and raw files under `resource/`. Raw assets are not assumed to be redistributable merely because they exist locally; add them only after their license and redistribution permission have been verified.

## Reproducing local media evidence

Install the media dependencies from `requirements-media.txt`, then use the shared commands documented in `docs/30-操作指南/统一媒体工具.md`. Downloaded media stays local and should not be added with `git add -f`.

## Repository status

This is a learning workspace rather than a packaged game release. Unity Editor version, render pipeline, evidence status, and licensing limitations are recorded in the project documentation and source records.
