"""Select deterministic incremental Capture v2 batches from the full Prefab technical corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


FAMILY_TERMS = {
    "fire": ("fire", "flame", "huo", "lava", "burn"),
    "lightning": ("lightning", "thunder", "electric", "leidian"),
    "slash": ("slash", "sword", "blade", "daoguang", "cut"),
    "explosion": ("explosion", "explode", "boom", "burst", "baozha"),
    "smoke": ("smoke", "cloud", "dust", "yanwu"),
    "water": ("water", "splash", "wave", "fluid"),
    "ice": ("ice", "frost", "snow", "bing"),
    "shield": ("shield", "barrier", "protect"),
    "magic_circle": ("magic", "rune", "circle", "portal"),
    "projectile": ("projectile", "bullet", "missile", "arrow"),
}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _family(path: str) -> str:
    lowered = path.lower().replace("_", "")
    matches = [family for family, terms in FAMILY_TERMS.items() if any(term.replace("_", "") in lowered for term in terms)]
    return matches[0] if matches else "unclassified"


def _complexity_bucket(row: dict[str, Any]) -> str:
    value = max(1, int(row.get("particle_system_count") or 0) + int(row.get("renderer_count") or 0))
    return f"c{min(5, int(math.log2(value)))}"


def _prior_prefabs(paths: Iterable[Path]) -> set[str]:
    result = set()
    for path in paths:
        payload = _read_json(path.resolve())
        for row in payload.get("selected") or []:
            result.add(str(row.get("prefab_path") or "").lower())
    return result


def prepare_capture_batch(
    baseline_root: Path,
    project_root: Path,
    output_root: Path,
    batch_id: str,
    *,
    count: int = 64,
    seed: int = 20260902,
    previous_manifests: Iterable[Path] = (),
    prefab_paths: Iterable[str] = (),
) -> dict[str, Path]:
    baseline_root, project_root, output_root = baseline_root.resolve(), project_root.resolve(), output_root.resolve()
    if count < 1:
        raise ValueError("capture batch count must be positive")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"capture batch output already exists and is not empty: {output_root}")
    baseline = _read_json(baseline_root / "technical_baseline_manifest.json")
    if baseline.get("status") != "pass" or baseline.get("quality_gates", {}).get("technical_coverage") != 1.0:
        raise ValueError("full technical baseline with 100% coverage required")
    rows = _read_jsonl(baseline_root / "technical_records.jsonl")
    previous = _prior_prefabs(previous_manifests)
    all_eligible = [
        row for row in rows
        if row.get("technical_status") == "particle_playable"
        and int(row.get("missing_script_count") or 0) == 0
        and int(row.get("missing_material_slot_count") or 0) == 0
        and int(row.get("missing_shader_count") or 0) == 0
        and row.get("source_group") != "VFXGenerated"
    ]
    requested_paths = [str(path) for path in prefab_paths if str(path).strip()]
    requested_keys = {path.lower() for path in requested_paths}
    eligible = [row for row in all_eligible if str(row.get("prefab_path") or "").lower() not in previous]
    rows_by_path = {str(row["prefab_path"]).lower(): row for row in all_eligible}
    missing_requested = sorted(requested_keys - set(rows_by_path), key=str.casefold)
    if missing_requested:
        raise ValueError(f"requested Prefab path is not a playable baseline asset: {missing_requested[0]}")
    buckets: dict[tuple[str, str, str], deque[dict[str, Any]]] = {}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        grouped[(str(row["source_group"]), _family(str(row["prefab_path"])), _complexity_bucket(row))].append(row)
    for key, values in grouped.items():
        values.sort(key=lambda row: hashlib.sha256(f"{seed}|{row['prefab_path']}".encode("utf-8")).hexdigest())
        buckets[key] = deque(values)
    selected = []
    selected_paths: set[str] = set()
    explicit_selection = bool(requested_keys)
    if explicit_selection:
        for path in requested_paths:
            key = path.lower()
            if key in selected_paths:
                continue
            selected.append(rows_by_path[key])
            selected_paths.add(key)
        count = len(selected)
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_source[str(row["source_group"])].append(row)
        by_family[_family(str(row["prefab_path"]))].append(row)
    if not explicit_selection:
        for values in (*[by_source[key] for key in sorted(by_source)], *[by_family[key] for key in sorted(by_family)]):
            candidate = min(values, key=lambda row: hashlib.sha256(f"{seed}|coverage|{row['prefab_path']}".encode("utf-8")).hexdigest())
            path = str(candidate["prefab_path"]).lower()
            if path not in selected_paths and len(selected) < count:
                selected.append(candidate)
                selected_paths.add(path)
        keys = sorted(buckets)
        while len(selected) < min(count, len(eligible)) and keys:
            next_keys = []
            for key in keys:
                while buckets[key] and str(buckets[key][0]["prefab_path"]).lower() in selected_paths:
                    buckets[key].popleft()
                if buckets[key] and len(selected) < count:
                    candidate = buckets[key].popleft()
                    selected.append(candidate)
                    selected_paths.add(str(candidate["prefab_path"]).lower())
                if buckets[key]:
                    next_keys.append(key)
            keys = next_keys
    request_rows = []
    selected_manifest = []
    for index, row in enumerate(selected, start=1):
        prefab_path = str(row["prefab_path"])
        candidate_id = f"full_prefab_{index:04d}_" + hashlib.sha256(prefab_path.encode("utf-8")).hexdigest()[:12]
        candidate_root = output_root / "cases" / candidate_id
        family = _family(prefab_path)
        request_rows.append({
            "candidate_id": candidate_id,
            "prefab_path": prefab_path,
            "capture_dir": (candidate_root / "captures").as_posix(),
            "capture_manifest_path": (candidate_root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (candidate_root / "material_timeline.json").as_posix(),
            "source_script_fidelity": "no_missing_scripts_unity_audit",
            "ignored_script_dependency_count": 0,
            "missing_script_count": 0,
            "capture_category": family,
        })
        selected_manifest.append({
            "candidate_id": candidate_id,
            "prefab_path": prefab_path,
            "source_group": row["source_group"],
            "effect_family_hint": family,
            "complexity_bucket": _complexity_bucket(row),
            "particle_system_count": row["particle_system_count"],
            "renderer_count": row["renderer_count"],
            "technical_status": row["technical_status"],
        })
    request = {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": batch_id,
        "unity_project": project_root.as_posix(),
        "scene": "FullPrefabCaptureV2",
        "camera": "FullPrefabCaptureV2Camera",
        "width": 640,
        "height": 360,
        "time_points_seconds": [],
        "sampling_mode": "adaptive_runtime",
        "sampling": {"target_intervals": 10, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.1, "max_duration_seconds": 3.0, "include_zero": True, "duration_sources": ["particle_system", "animator", "animation", "playable_director", "trail_renderer", "custom_script_unknown"]},
        "capture_material_timeline": True,
        "requests": request_rows,
    }
    request_path = _write_json(output_root / "render_requests.json", request)
    paths = [row["prefab_path"].lower() for row in selected_manifest]
    gates = {
        "duplicate_prefabs": len(paths) - len(set(paths)),
        "non_playable_selected": sum(row["technical_status"] != "particle_playable" for row in selected_manifest),
        "missing_prefab_files": sum(not (project_root / Path(row["prefab_path"])).is_file() for row in selected_manifest),
        "generated_prefabs_selected": sum(row["source_group"] == "VFXGenerated" for row in selected_manifest),
    }
    if any(gates.values()):
        raise ValueError(f"capture batch quality gate failed: {gates}")
    manifest = {
        "schema_version": "vfx_full_prefab_capture_batch.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_baseline": _portable(baseline_root / "technical_baseline_manifest.json"),
        "eligible_count": len(eligible),
        "selected_count": len(selected_manifest),
        "excluded_previous_count": len(previous),
        "source_group_counts": dict(sorted(Counter(row["source_group"] for row in selected_manifest).items())),
        "effect_family_counts": dict(sorted(Counter(row["effect_family_hint"] for row in selected_manifest).items())),
        "technical_status_counts": dict(sorted(Counter(row["technical_status"] for row in selected_manifest).items())),
        "selected": selected_manifest,
        "request_path": _portable(request_path),
        "selection_policy": "explicit_prefab_paths.v1" if explicit_selection else "deterministic_source_family_complexity_round_robin.v1",
        "quality_gates": gates,
        "status": "pass",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/full_prefab_capture_batch.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise ValueError(f"capture batch manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_root / "capture_batch_manifest.json", manifest)
    return {"manifest": manifest_path, "request": request_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a deterministic incremental Capture v2 Prefab batch.")
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--count", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--previous-manifest", type=Path, action="append", default=[])
    parser.add_argument("--prefab-path", action="append", default=[], help="Recapture explicit playable Prefab paths, including paths present in previous batches.")
    args = parser.parse_args(argv)
    try:
        paths = prepare_capture_batch(args.baseline_root, args.project_root, args.output_root, args.batch_id, count=args.count, seed=args.seed, previous_manifests=args.previous_manifest, prefab_paths=args.prefab_path)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
