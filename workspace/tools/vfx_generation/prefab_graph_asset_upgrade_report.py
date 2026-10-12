"""Build a verified report for constrained Graph asset-upgrade runs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _portable(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return path.resolve().as_posix()


def build_report(upgrade_root: Path, capture_root: Path, output_path: Path) -> Path:
    upgrade_root = upgrade_root.resolve()
    capture_root = capture_root.resolve()
    repo_root = Path(__file__).parents[3].resolve()
    upgrade = _read(upgrade_root / "upgrade_manifest.json")
    rows: list[dict[str, Any]] = []
    for candidate in upgrade["candidates"]:
        candidate_id = str(candidate["candidate_id"])
        profile = str(candidate["profile"])
        compile_result = _read(upgrade_root / "compile_results" / f"{profile}.json")
        capture = _read(capture_root / profile / "capture_manifest.json")
        rows.append({
            "candidate_id": candidate_id,
            "profile": profile,
            "graph_path": candidate["graph_path"],
            "asset_plan_path": candidate["asset_plan_path"],
            "prefab_path": compile_result["output_prefab_path"],
            "parent_prefab_path": candidate["parent_prefab_path"],
            "compile_status": compile_result["status"],
            "source_prefab_read": compile_result["source_prefab_read"],
            "node_count": compile_result["node_count"],
            "particle_system_count": compile_result["particle_system_count"],
            "generated_material_count": len(compile_result.get("generated_material_paths") or []),
            "generated_texture_count": len(compile_result.get("generated_texture_paths") or []),
            "shader_names": sorted(set(compile_result.get("generated_shader_names") or [])),
            "valid_frame_count": capture["valid_frame_count"],
            "frame_count": len(capture["frames"]),
            "render_error": capture.get("render_error"),
            "visual_expectation": "no_particle_visual" if profile == "root_only" else "visible_candidate",
        })
    rows.sort(key=lambda value: value["profile"])
    report = {
        "schema_version": "vfx_prefab_graph_asset_upgrade_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "upgrade_manifest": _portable(upgrade_root / "upgrade_manifest.json", repo_root),
        "capture_root": _portable(capture_root, repo_root),
        "candidate_count": len(rows),
        "compile_status_counts": dict(sorted(Counter(row["compile_status"] for row in rows).items())),
        "rows": rows,
        "quality_gates": {
            "expected_profiles": ["root_only", "particle_v1", "multi_particle"],
            "profiles_present": sorted(row["profile"] for row in rows),
            "all_compile_pass": all(row["compile_status"] == "pass" for row in rows),
            "all_no_parent_source_read": all(row["source_prefab_read"] is False and row["parent_prefab_path"] is None for row in rows),
            "all_capture_frames_valid": all(row["valid_frame_count"] == row["frame_count"] and row["frame_count"] == 9 for row in rows),
            "particle_candidates_have_generated_assets": all(
                row["generated_material_count"] > 0 and row["generated_texture_count"] > 0 for row in rows if row["profile"] != "root_only"
            ),
            "unity_render_errors_empty": all(not row["render_error"] for row in rows),
        },
        "training_scope": "technical asset routing and compiler validation; AI hypotheses only; no human aesthetic or preference labels",
        "status": "pass" if len(rows) == 3 and sorted(row["profile"] for row in rows) == ["multi_particle", "particle_v1", "root_only"] and all(
            row["compile_status"] == "pass" and row["source_prefab_read"] is False and row["parent_prefab_path"] is None and row["valid_frame_count"] == row["frame_count"] == 9 and not row["render_error"] for row in rows
        ) else "blocked",
    }
    schema_path = repo_root / "workspace/data/vfx_generation/schemas/prefab_graph_asset_upgrade_report.schema.json"
    schema = _read(schema_path)
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        raise ValueError(f"asset upgrade report schema error: {errors[0].message}")
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a verified PrefabGraph asset-upgrade report.")
    parser.add_argument("--upgrade-root", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = build_report(args.upgrade_root, args.capture_root, args.output)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "report": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
