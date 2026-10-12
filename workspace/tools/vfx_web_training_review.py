"""Build the metadata bridge between a VFX run and the WebGL review player."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


BUNDLE_SCHEMA_VERSION = "vfx_web_training_review_bundle.v1"
ASSET_MAP_SCHEMA_VERSION = "vfx_web_training_asset_map.v1"
CATALOG_SCHEMA_VERSION = "vfx_web_review_catalog.v1"
SCHEMA_PATH = Path(__file__).parents[1] / "data/vfx_generation/schemas/vfx_web_training_review_bundle.schema.json"
_GUID_PATTERN = re.compile(r"^guid:\s*([0-9a-f]{32})\s*$", re.MULTILINE)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _resolve_path(value: Any, base: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _path_text(path: Path | None, base: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _candidate_spec(run_root: Path, candidate: dict[str, Any]) -> tuple[Path | None, dict[str, Any]]:
    spec_path = _resolve_path(candidate.get("spec_path"), run_root)
    if spec_path is None or not spec_path.is_file():
        return spec_path, {}
    return spec_path, _read_json(spec_path)


def _source_prefab_path(spec: dict[str, Any]) -> str | None:
    for layer in spec.get("layers", []) if isinstance(spec.get("layers"), list) else []:
        if not isinstance(layer, dict):
            continue
        shape = layer.get("shape_parameters")
        if isinstance(shape, dict) and isinstance(shape.get("source_prefab_path"), str):
            return shape["source_prefab_path"]
    return None


def _timeline_path(run_root: Path, candidate: dict[str, Any]) -> Path | None:
    direct = _resolve_path(candidate.get("material_timeline_path"), run_root)
    if direct is not None:
        return direct
    render_manifest_path = _resolve_path(candidate.get("render_manifest_path"), run_root)
    if render_manifest_path is None or not render_manifest_path.is_file():
        return None
    render_manifest = _read_json(render_manifest_path)
    return _resolve_path(render_manifest.get("material_timeline_path"), render_manifest_path.parent)


def _timeline_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "not_linked",
            "change_count": 0,
            "key_times": [],
            "source_script_fidelity": "unknown",
        }
    if not path.is_file():
        return {
            "status": "missing",
            "change_count": 0,
            "key_times": [],
            "source_script_fidelity": "unknown",
        }

    timeline = _read_json(path)
    frames = timeline.get("frames") if isinstance(timeline.get("frames"), list) else []
    change_count = timeline.get("delta_count")
    if not isinstance(change_count, int):
        change_count = sum(
            len(frame.get("deltas_from_previous", []))
            for frame in frames
            if isinstance(frame, dict) and isinstance(frame.get("deltas_from_previous"), list)
        )
    key_times = timeline.get("key_material_change_times")
    if not isinstance(key_times, list):
        key_times = []
        for frame in frames:
            if not isinstance(frame, dict) or not frame.get("deltas_from_previous"):
                continue
            value = frame.get("capture_time_seconds", frame.get("requested_time_seconds"))
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                key_times.append(round(float(value), 4))
    key_times = sorted({round(float(value), 4) for value in key_times if isinstance(value, (int, float)) and not isinstance(value, bool)})
    return {
        "status": "ready",
        "change_count": max(0, change_count),
        "key_times": key_times,
        "source_script_fidelity": str(timeline.get("source_script_fidelity") or "unknown"),
    }


def validate_bundle(bundle: dict[str, Any]) -> None:
    schema = _read_json(SCHEMA_PATH)
    errors = sorted(Draft202012Validator(schema).iter_errors(bundle), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.path) or "root"
        raise ValueError(f"invalid WebGL training review bundle at {location}: {first.message}")


def build_asset_map(run_manifest_path: Path, review_bundle_id: str | None = None) -> dict[str, Any]:
    """Create the complete asset map for a Play Mode verified Prefab run."""
    run_manifest_path = run_manifest_path.resolve()
    run_root = run_manifest_path.parent
    run_manifest = _read_json(run_manifest_path)
    if run_manifest.get("capture_mode") != "play_mode_runtime":
        raise ValueError("WebGL review asset maps require play_mode_runtime capture evidence")

    mappings: list[dict[str, str]] = []
    seen_candidates: set[str] = set()
    seen_prefabs: set[str] = set()
    for candidate in run_manifest.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen_candidates:
            raise ValueError(f"invalid or repeated run candidate: {candidate_id or '<empty>'}")
        if candidate.get("material_timeline_status") != "ready":
            raise ValueError(f"candidate has no ready material timeline: {candidate_id}")
        spec_path, spec = _candidate_spec(run_root, candidate)
        source_prefab_path = _source_prefab_path(spec)
        if not source_prefab_path or not source_prefab_path.startswith("Assets/"):
            raise ValueError(f"candidate has no Unity Assets source Prefab path: {candidate_id} ({spec_path})")
        normalized_path = source_prefab_path.replace("\\", "/")
        if normalized_path in seen_prefabs:
            raise ValueError(f"multiple candidates map to the same Prefab: {normalized_path}")
        seen_candidates.add(candidate_id)
        seen_prefabs.add(normalized_path)
        mappings.append({
            "candidateId": candidate_id,
            "webPrefabPath": normalized_path,
            "sourcePrefabPath": normalized_path,
        })

    if not mappings:
        raise ValueError("run manifest has no WebGL-mappable candidates")
    return {
        "schemaVersion": ASSET_MAP_SCHEMA_VERSION,
        "reviewBundleId": review_bundle_id or f"{run_manifest.get('run_id')}_web_review",
        "mappings": mappings,
    }


def _guid_for_asset(unity_project: Path, asset_path: str) -> str:
    if not asset_path.startswith("Assets/"):
        raise ValueError(f"WebGL asset path must be under Assets/: {asset_path}")
    source_path = unity_project / asset_path
    meta_path = Path(str(source_path) + ".meta")
    if not source_path.is_file() or not meta_path.is_file():
        raise FileNotFoundError(f"WebGL Prefab or .meta is missing: {source_path}")
    match = _GUID_PATTERN.search(meta_path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"Prefab .meta has no Unity GUID: {meta_path}")
    return match.group(1)


def _review_candidate_index(dataset_root: Path | None) -> dict[str, str]:
    if dataset_root is None:
        return {}
    examples_path = dataset_root.resolve() / "examples.jsonl"
    if not examples_path.is_file():
        raise FileNotFoundError(f"Prefab review dataset is missing examples.jsonl: {examples_path}")
    result: dict[str, str] = {}
    for line in examples_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        example = json.loads(line)
        if not isinstance(example, dict):
            raise ValueError("Prefab review dataset examples must be JSON objects")
        candidate_id = str(example.get("candidate_id") or "")
        inputs = example.get("inputs") if isinstance(example.get("inputs"), dict) else {}
        prefab_path = str(inputs.get("prefab_path") or "").replace("\\", "/")
        if not candidate_id or not prefab_path:
            raise ValueError("Prefab review dataset example has no candidate_id or prefab_path")
        if prefab_path in result and result[prefab_path] != candidate_id:
            raise ValueError(f"Prefab review dataset repeats Prefab path: {prefab_path}")
        result[prefab_path] = candidate_id
    return result


def build_catalog_manifest(
    asset_map_path: Path,
    unity_project: Path,
    player_url: str,
    dataset_root: Path | None = None,
) -> dict[str, Any]:
    """Materialize the deterministic AssetDatabase GUID ids used by the WebGL catalog."""
    asset_map = _read_json(asset_map_path.resolve())
    if asset_map.get("schemaVersion") != ASSET_MAP_SCHEMA_VERSION:
        raise ValueError(f"unsupported WebGL asset map: {asset_map.get('schemaVersion')}")
    project = unity_project.resolve()
    if not (project / "Assets").is_dir():
        raise ValueError(f"not a Unity project: {project}")
    if not player_url.startswith(("http://", "https://")):
        raise ValueError(f"WebGL player URL must be http(s): {player_url}")
    review_candidates = _review_candidate_index(dataset_root)

    entries: list[dict[str, str]] = []
    seen_candidates: set[str] = set()
    seen_catalog_ids: set[str] = set()
    for mapping in asset_map.get("mappings", []):
        if not isinstance(mapping, dict):
            raise ValueError("asset map mappings must be objects")
        candidate_id = str(mapping.get("candidateId") or "")
        prefab_path = str(mapping.get("webPrefabPath") or mapping.get("sourcePrefabPath") or "").replace("\\", "/")
        if not candidate_id or candidate_id in seen_candidates:
            raise ValueError(f"invalid or repeated WebGL candidate: {candidate_id or '<empty>'}")
        catalog_id = _guid_for_asset(project, prefab_path)
        if catalog_id in seen_catalog_ids:
            raise ValueError(f"multiple WebGL candidates resolve to the same catalog id: {catalog_id}")
        review_candidate_id = review_candidates.get(prefab_path, candidate_id)
        if dataset_root is not None and review_candidate_id == candidate_id and prefab_path not in review_candidates:
            raise ValueError(f"WebGL Prefab is absent from the review dataset: {prefab_path}")
        seen_candidates.add(candidate_id)
        seen_catalog_ids.add(catalog_id)
        entries.append({
            "candidateId": candidate_id,
            "reviewCandidateId": review_candidate_id,
            "webPrefabPath": prefab_path,
            "sourcePrefabPath": str(mapping.get("sourcePrefabPath") or prefab_path).replace("\\", "/"),
            "catalogId": catalog_id,
        })

    if not entries:
        raise ValueError("asset map has no entries")
    return {
        "schemaVersion": CATALOG_SCHEMA_VERSION,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "reviewBundleId": str(asset_map.get("reviewBundleId") or ""),
        "playerUrl": player_url.rstrip("/") + "/",
        "entries": entries,
    }


def build_review_bundle(run_manifest_path: Path, asset_map_path: Path) -> dict[str, Any]:
    run_manifest_path = run_manifest_path.resolve()
    run_root = run_manifest_path.parent
    run_manifest = _read_json(run_manifest_path)
    asset_map = _read_json(asset_map_path.resolve())
    if asset_map.get("schemaVersion") != ASSET_MAP_SCHEMA_VERSION:
        raise ValueError(f"unsupported WebGL asset map: {asset_map.get('schemaVersion')}")

    candidates = {
        str(candidate.get("candidate_id")): candidate
        for candidate in run_manifest.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("candidate_id")
    }
    entries: list[dict[str, Any]] = []
    mapped_ids: set[str] = set()
    for mapping in asset_map.get("mappings", []):
        if not isinstance(mapping, dict):
            raise ValueError("asset map mappings must be objects")
        candidate_id = str(mapping.get("candidateId") or "")
        if candidate_id not in candidates:
            raise ValueError(f"asset map references unknown candidate: {candidate_id}")
        if candidate_id in mapped_ids:
            raise ValueError(f"asset map repeats candidate: {candidate_id}")
        mapped_ids.add(candidate_id)

        candidate = candidates[candidate_id]
        spec_path, spec = _candidate_spec(run_root, candidate)
        timeline_path = _timeline_path(run_root, candidate)
        timeline = _timeline_summary(timeline_path)
        generation = spec.get("generation") if isinstance(spec.get("generation"), dict) else {}
        spec_summary = candidate.get("spec_summary") if isinstance(candidate.get("spec_summary"), dict) else {}
        entry = {
            "webPrefabPath": str(mapping.get("webPrefabPath") or "").replace("\\", "/"),
            "sourcePrefabPath": str(mapping.get("sourcePrefabPath") or _source_prefab_path(spec) or "").replace("\\", "/"),
            "runId": str(run_manifest.get("run_id") or ""),
            "candidateId": candidate_id,
            "trainingCaseId": str(mapping.get("trainingCaseId") or spec.get("training_case_id") or ""),
            "effectFamily": str(spec.get("effect_family") or spec_summary.get("effect_family") or "unknown"),
            "materialTimelinePath": _path_text(timeline_path, run_root),
            "materialTimelineStatus": timeline["status"],
            "materialChangeCount": timeline["change_count"],
            "materialKeyTimes": timeline["key_times"],
            "sourceScriptFidelity": str(mapping.get("sourceScriptFidelity") or timeline["source_script_fidelity"]),
            "specPath": _path_text(spec_path, run_root),
            "renderManifestPath": candidate.get("render_manifest_path"),
            "hasSeed": isinstance(candidate.get("seed"), int) and not isinstance(candidate.get("seed"), bool),
            "seed": int(candidate.get("seed") or 0),
            "generator": generation.get("generator") or spec_summary.get("generator"),
            "generatorVersion": generation.get("generator_version") or spec_summary.get("generator_version"),
        }
        if not entry["webPrefabPath"] and not entry["sourcePrefabPath"]:
            raise ValueError(f"asset map must provide a WebGL Prefab path for {candidate_id}")
        entries.append(entry)

    bundle = {
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "reviewBundleId": str(asset_map.get("reviewBundleId") or f"{run_manifest.get('run_id')}_web_review"),
        "runId": str(run_manifest.get("run_id") or ""),
        "sourceUnityProject": str(run_manifest.get("unity_project") or ""),
        "truthCaptureMode": str(run_manifest.get("capture_mode") or "unknown"),
        "entries": entries,
    }
    validate_bundle(bundle)
    return bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a WebGL dynamic-review bundle from a VFX run manifest.")
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--asset-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build auditable WebGL review mappings and bundles.")
    commands = parser.add_subparsers(dest="command", required=True)
    bundle = commands.add_parser("bundle")
    bundle.add_argument("--run-manifest", type=Path, required=True)
    bundle.add_argument("--asset-map", type=Path, required=True)
    bundle.add_argument("--output", type=Path, required=True)
    asset_map = commands.add_parser("asset-map")
    asset_map.add_argument("--run-manifest", type=Path, required=True)
    asset_map.add_argument("--output", type=Path, required=True)
    asset_map.add_argument("--review-bundle-id")
    catalog = commands.add_parser("catalog")
    catalog.add_argument("--asset-map", type=Path, required=True)
    catalog.add_argument("--unity-project", type=Path, required=True)
    catalog.add_argument("--dataset-root", type=Path)
    catalog.add_argument("--player-url", required=True)
    catalog.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "bundle":
            payload = build_review_bundle(args.run_manifest, args.asset_map)
        elif args.command == "asset-map":
            payload = build_asset_map(args.run_manifest, args.review_bundle_id)
        else:
            payload = build_catalog_manifest(args.asset_map, args.unity_project, args.player_url, args.dataset_root)
        output = _write_json(args.output.resolve(), payload)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "output": output.as_posix(), "entry_count": len(payload["entries"]) if "entries" in payload else len(payload["mappings"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
