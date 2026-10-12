"""Build a persistent human-review batch for material-timeline WebGL candidates."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_SCHEMA = "prefab_human_review_batch.v3"
STORE_SCHEMA = "prefab_human_feedback_store.v2"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr", ".dds", ".psd", ".bmp"}
GUID_PATTERN = re.compile(r"guid:\s*([0-9a-fA-F]{32})")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def portable(path: Path) -> str:
    root = repo_root()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def source_prefab(spec: dict[str, Any]) -> str:
    for layer in spec.get("layers", []):
        if not isinstance(layer, dict):
            continue
        shape = layer.get("shape_parameters")
        if isinstance(shape, dict) and shape.get("source_prefab_path"):
            return str(shape["source_prefab_path"]).replace("\\", "/")
    raise ValueError("material-timeline spec has no source Prefab path")


def load_catalog(path: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    catalog = read_json(path)
    if catalog.get("schemaVersion") != "vfx_web_review_catalog.v1":
        raise ValueError(f"unsupported WebGL catalog: {path}")
    player_url = str(catalog.get("playerUrl") or "")
    if not player_url.startswith(("http://", "https://")):
        raise ValueError(f"WebGL catalog has no player URL: {path}")
    result = {}
    for entry in catalog.get("entries", []):
        if not isinstance(entry, dict) or not entry.get("candidateId"):
            raise ValueError(f"invalid catalog entry: {path}")
        result[str(entry["candidateId"])] = entry
    if not result:
        raise ValueError("WebGL catalog has no entries")
    return player_url.rstrip("/") + "/", result


def normalize_asset_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("./")


def load_prefab_audit(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    audit = read_json(path)
    if not isinstance(audit.get("prefabs"), list):
        raise ValueError(f"Prefab audit has no prefabs list: {path}")
    result = {}
    for record in audit["prefabs"]:
        if not isinstance(record, dict) or not record.get("prefab_path"):
            continue
        result[normalize_asset_path(record["prefab_path"])] = record
    return result


def load_texture_guid_index(unity_project: Path | None) -> dict[str, str]:
    if unity_project is None:
        return {}
    result: dict[str, str] = {}
    for meta_path in unity_project.rglob("*.meta"):
        asset_path = meta_path.with_suffix("")
        if asset_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            text = meta_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = GUID_PATTERN.search(text)
        if match:
            result[match.group(1).lower()] = normalize_asset_path(asset_path.relative_to(unity_project))
    return result


def material_paths_from(audit_record: dict[str, Any] | None, spec: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    if audit_record:
        for renderer in audit_record.get("renderers", []):
            if not isinstance(renderer, dict):
                continue
            paths.update(normalize_asset_path(value) for value in renderer.get("material_paths", []))
    if not paths:
        for layer in spec.get("layers", []):
            if not isinstance(layer, dict):
                continue
            selection = (layer.get("material_parameters") or {}).get("material_selection") or {}
            for material in selection.get("materials", []):
                if isinstance(material, dict):
                    value = material.get("material_path") or material.get("path")
                    if value:
                        paths.add(normalize_asset_path(value))
    return sorted(value for value in paths if value)


def count_material_textures(
    material_paths: list[str],
    unity_project: Path | None,
    texture_guid_index: dict[str, str],
) -> int:
    if unity_project is None or not texture_guid_index:
        return 0
    texture_guids: set[str] = set()
    for material_path in material_paths:
        path = unity_project / material_path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        texture_guids.update(
            match.group(1).lower()
            for match in GUID_PATTERN.finditer(text)
            if match.group(1).lower() in texture_guid_index
        )
    return len(texture_guids)


def build_batch(
    run_root: Path,
    catalog_path: Path,
    output_root: Path,
    batch_id: str,
    prefab_audit_path: Path | None = None,
    unity_project: Path | None = None,
) -> dict[str, str]:
    run_root = run_root.resolve()
    catalog_path = catalog_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"review output already exists and is not empty: {output_root}")

    run_manifest = read_json(run_root / "run_manifest.json")
    player_url, catalog = load_catalog(catalog_path)
    prefab_audit = load_prefab_audit(prefab_audit_path.resolve() if prefab_audit_path else None)
    texture_guid_index = load_texture_guid_index(unity_project.resolve() if unity_project else None)
    records: list[dict[str, Any]] = []
    for index, candidate in enumerate(run_manifest.get("candidates", []), start=1):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id not in catalog:
            continue
        spec_path = run_root / str(candidate.get("spec_path") or "")
        spec = read_json(spec_path)
        prefab_path = source_prefab(spec)
        audit_record = prefab_audit.get(normalize_asset_path(prefab_path))
        material_paths = material_paths_from(audit_record, spec)
        capture_root = run_root / str(candidate.get("capture_root") or "")
        frames: list[dict[str, Any]] = []
        for frame in candidate.get("frames", []):
            if not isinstance(frame, dict):
                continue
            frame_path = capture_root / str(frame.get("path") or "")
            if not frame_path.is_file():
                raise FileNotFoundError(f"material-timeline frame is missing: {frame_path}")
            frames.append({
                "time_seconds": float(frame.get("requested_time_seconds", 0.0)),
                "path": portable(frame_path),
            })
        if not frames:
            raise ValueError(f"material-timeline candidate has no frames: {candidate_id}")
        auto_eval = candidate.get("auto_eval") if isinstance(candidate.get("auto_eval"), dict) else {
            "status": "unknown",
            "metrics": {},
            "hard_reject_reasons": [],
        }
        metrics = auto_eval.get("metrics") if isinstance(auto_eval.get("metrics"), dict) else {}
        visible_peak = float(metrics.get("visible_area_ratio_peak") or 0.0)
        source_category = ["ui"] if "/UI/" in prefab_path else ["battle"]
        timeline = candidate.get("material_state_summary") if isinstance(candidate.get("material_state_summary"), dict) else {}
        preview = dict(catalog[candidate_id])
        preview.update({
            "status": "webgl_ready",
            "status_cn": "真实 WebGL 预览可用",
            "availability_reason_cn": "该候选已关联真实 Unity 2022 WebGL Prefab，可在动态预览中复核。",
            "player_url": player_url,
            "catalog_id": str(preview.get("catalogId") or ""),
            "source_prefab_path": str(preview.get("sourcePrefabPath") or prefab_path),
        })
        summary = dict(audit_record or {})
        particle_system_count = int(summary.get("particle_system_count") or preview.get("particleSystemCount") or 0)
        renderer_count = int(summary.get("renderer_count") or preview.get("rendererCount") or 0)
        material_slot_count = int(summary.get("material_slot_count") or len(material_paths))
        texture_count = count_material_textures(material_paths, unity_project, texture_guid_index)
        material_count = len(material_paths) or material_slot_count
        records.append({
            "candidate_id": candidate_id,
            "prefab_path": prefab_path,
            "source_category": source_category,
            "effect_family_hint": str(candidate.get("spec_summary", {}).get("effect_family") or "source_ingest"),
            "technical_status": "particle_playable",
            "technical_status_cn": "可独立播放",
            "review_route": "可评价",
            "visibility_status": "可见" if visible_peak > 0 else "主体过小",
            "auto_eval": auto_eval,
            "auto_eval_status_cn": "主体偏小" if str(auto_eval.get("status")) == "warn" else "自动可见",
            "prefab_summary": {
                "status": str(summary.get("status") or "particle_playable"),
                "particle_system_count": particle_system_count,
                "particle_renderer_count": int(summary.get("particle_renderer_count") or 0),
                "renderer_count": renderer_count,
                "material_slot_count": material_slot_count,
                "missing_script_count": int(summary.get("missing_script_count") or 0),
                "missing_material_slot_count": int(summary.get("missing_material_slot_count") or 0),
                "serialized_empty_material_slot_count": int(summary.get("serialized_empty_material_slot_count") or 0),
                "missing_shader_count": int(summary.get("missing_shader_count") or 0),
                "estimated_duration_seconds": summary.get("estimated_duration_seconds"),
                "looping": summary.get("looping"),
            },
            "particle_system_count": particle_system_count,
            "material_count": material_count,
            "texture_count": texture_count,
            "frames": frames,
            "contact_sheet_path": portable(run_root / "contact_sheets/page-001.jpg"),
            "feedback_status": "pending",
            "webgl_preview": preview,
            "material_timeline_status": str(candidate.get("material_timeline_status") or "ready"),
            "material_change_count": int(timeline.get("delta_count") or 0),
            "material_key_times": timeline.get("key_material_change_times") or [],
            "material_timeline_path": portable(run_root / str(candidate.get("material_timeline_path") or "")),
            "review_index": index,
        })
    records.sort(key=lambda row: row["candidate_id"])
    if not records:
        raise ValueError("catalog does not select any material-timeline candidates")

    statuses = Counter(str(row["webgl_preview"]["status"]) for row in records)
    batch = {
        "schema_version": REVIEW_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_dataset": portable(run_root / "run_manifest.json"),
        "source_run": portable(run_root / "run_manifest.json"),
        "selection_strategy": "material_timeline_webgl_review.v1",
        "requested_count": len(records),
        "selected_count": len(records),
        "review_route_counts": {"可评价": len(records)},
        "technical_status_counts": {"particle_playable": len(records)},
        "webgl_catalog": portable(catalog_path),
        "prefab_audit": portable(prefab_audit_path) if prefab_audit_path else None,
        "unity_project": portable(unity_project) if unity_project else None,
        "webgl_status_counts": dict(sorted(statuses.items())),
        "records": records,
    }
    write_json(output_root / "review_batch.json", batch)
    write_json(output_root / "feedback_store.json", {
        "schema_version": STORE_SCHEMA,
        "batch_id": batch_id,
        "records": {},
    })
    write_jsonl(output_root / "feedback.jsonl", [])
    return {
        "review_batch": portable(output_root / "review_batch.json"),
        "feedback_store": portable(output_root / "feedback_store.json"),
        "feedback": portable(output_root / "feedback.jsonl"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--prefab-audit", type=Path)
    parser.add_argument("--unity-project", type=Path)
    args = parser.parse_args()
    try:
        result = build_batch(
            args.run_root,
            args.catalog,
            args.output_root,
            args.batch_id,
            args.prefab_audit,
            args.unity_project,
        )
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
