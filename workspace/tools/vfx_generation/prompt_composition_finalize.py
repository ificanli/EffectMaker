"""Finalize true Prefab plus MaterialTrajectory compositions without inventing prompt-quality labels."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from PIL import Image, ImageDraw, ImageFont

from workspace.tools.vfx_generation.run_pipeline import _frame_image_stats


VISIBLE_THRESHOLD = 0.001


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    root = Path(__file__).parents[3].resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _frame_metrics(paths: list[Path]) -> tuple[float, float]:
    ratios = []
    for path in paths:
        with Image.open(path) as image:
            ratios.append(float(_frame_image_stats(image, background_relative=True)["visible_area_ratio"]))
    return max(ratios, default=0.0), sum(ratios) / len(ratios) if ratios else 0.0


def _contact_sheet(candidates: list[dict[str, Any]], output: Path) -> Path:
    width, row_height = 1280, 220
    canvas = Image.new("RGB", (width, row_height * len(candidates)), "#10151b")
    draw, font = ImageDraw.Draw(canvas), ImageFont.load_default()
    for index, candidate in enumerate(candidates):
        top = index * row_height
        frame = Path(candidate["representative_frame"])
        with Image.open(frame) as image:
            preview = image.convert("RGB")
            preview.thumbnail((300, 190))
            canvas.paste(preview, (15, top + 15))
        lines = [
            candidate["candidate_id"],
            Path(candidate["source_prefab"]["prefab_path"]).name,
            f"trajectory={candidate['material_trajectory']['trajectory_id']}",
            f"technical={candidate['execution_status']} visible={candidate['max_visible_area_ratio']:.5f}",
            "signals=" + ",".join(candidate["actual_signals"]),
            "unscored=" + ", ".join(candidate["prompt_conditions_unscored"]),
        ]
        draw.multiline_text((335, top + 18), "\n".join(lines), fill="white", font=font, spacing=6)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=90)
    return output


def finalize_composition(composition_root: Path, retrieval_manifest: Path) -> Path:
    composition_root = composition_root.resolve()
    retrieval_manifest = retrieval_manifest.resolve()
    request = _read_json(composition_root / "execution_requests.json")
    retrieval = _read_json(retrieval_manifest)
    lookup = {str(row["candidate_id"]): row for row in retrieval["candidates"]}
    candidates: list[dict[str, Any]] = []
    for request_item in request["requests"]:
        candidate_id = str(request_item["candidate_id"])
        proposal = lookup[candidate_id]
        candidate_root = composition_root / "candidates" / candidate_id
        result = _read_json(candidate_root / "execution_result.json")
        timeline = _read_json(candidate_root / "material_timeline.json")
        frames = [candidate_root / "frames" / str(frame["path"]) for frame in result["frames"]]
        if any(not path.is_file() for path in frames):
            raise FileNotFoundError(f"composition frame is missing for {candidate_id}")
        max_visible, mean_visible = _frame_metrics(frames)
        resources = result.get("resource_audit") or {}
        clean = int(resources.get("runtime_materials_live", -1)) == 0 and int(resources.get("runtime_textures_live", -1)) == 0
        technical = result.get("status") == "pass" and clean and result["valid_frame_count"] == len(result["frames"])
        visual = "visible" if max_visible >= VISIBLE_THRESHOLD else "near_blank"
        status = "technical_pass" if technical and visual == "visible" else "near_blank" if technical else "technical_fail"
        candidates.append({
            "candidate_id": candidate_id,
            "source_prefab": proposal["source_prefab"],
            "material_trajectory": proposal["material_trajectory"],
            "execution_status": status,
            "expected_signals": result["expected_signals"],
            "actual_signals": result["actual_signals"],
            "frame_count": len(result["frames"]),
            "valid_frame_count": result["valid_frame_count"],
            "visual_status": visual,
            "max_visible_area_ratio": round(max_visible, 8),
            "mean_visible_area_ratio": round(mean_visible, 8),
            "image_feature_eligible": technical and visual == "visible",
            "prompt_conditions_unscored": proposal["unmatched_conditions"],
            "resource_clean": clean,
            "representative_frame": str(max(frames, key=lambda path: path.stat().st_size)),
            "execution_result_path": _portable(candidate_root / "execution_result.json"),
            "material_timeline_path": _portable(candidate_root / "material_timeline.json"),
            "source_script_fidelity": timeline.get("source_script_fidelity"),
        })
    sheet = _contact_sheet(candidates, composition_root / "contact_sheet.jpg")
    all_technical = all(row["execution_status"] != "technical_fail" for row in candidates)
    manifest = {
        "schema_version": "prompt_composition_manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": request["run_id"],
        "retrieval_manifest_path": _portable(retrieval_manifest),
        "prompt_condition": retrieval["prompt_condition"],
        "candidate_count": len(candidates),
        "technical_pass_count": sum(row["execution_status"] != "technical_fail" for row in candidates),
        "visible_count": sum(row["visual_status"] == "visible" for row in candidates),
        "near_blank_count": sum(row["visual_status"] == "near_blank" for row in candidates),
        "human_aesthetic_labels_used": 0,
        "prompt_conditions_unscored": sorted({item for row in candidates for item in row["prompt_conditions_unscored"]}),
        "contact_sheet_paths": [_portable(sheet)],
        "candidates": candidates,
        "status": "technical_pass_prompt_unscored" if all_technical else "technical_fail",
    }
    schema_path = Path("workspace/data/vfx_generation/schemas/prompt_composition_manifest.schema.json")
    errors = list(Draft202012Validator(_read_json(schema_path)).iter_errors(manifest))
    if errors:
        raise ValueError(f"composition manifest schema error: {errors[0].message}")
    return _write_json(composition_root / "composition_manifest.json", manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--composition-root", type=Path, required=True)
    parser.add_argument("--retrieval-manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = finalize_composition(args.composition_root, args.retrieval_manifest)
    except (OSError, ValueError, FileNotFoundError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "manifest": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
