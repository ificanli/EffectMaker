# Unity Demo Projects

This folder contains the Unity project variants used in this workspace.

## Production projects

- `EffectDemo6.0/`
- Unity `6000.5.9f1`
- URP `17.5.0`
- Pipeline `com.unity.pipeline 0.5.0-exp.1`
- Unity 6 production track; Pipeline port `7800`

- `EffectDemo/`
- Unity `2022.3.16f1c1`
- URP `14.0.9`
- Embedded Unity 2022 Pipeline adaptation; Pipeline port `7801`
- Unity 2022 production track for older effects and cross-version comparison

## Project rules

- Keep the two tracks independent: never mix assets, scene edits, Library, Temp, logs, or
  editor versions.
- Open `EffectDemo6.0/` with Unity `6000.5.9f1` and `EffectDemo/` with Unity
  `2022.3.16f1c1`.
- Use the Pipeline port reported by `unity status`; do not send a command for one project to
  the other project's Editor.
- When a task targets a specific engine version, record that version and render pipeline in the
  effect experiment and validation evidence.
