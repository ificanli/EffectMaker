"""Deterministic Prompt-conditioned retrieval baseline over verified Prefab and Material examples."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from PIL import Image, ImageDraw, ImageFont


STYLE_TERMS = {
    "realistic": ("写实", "realistic"), "stylized": ("风格化", "stylized"),
    "cartoon": ("卡通", "cartoon"), "anime": ("动漫", "二次元", "anime"),
    "fantasy_painterly": ("国风", "幻想", "fantasy", "painterly"), "ui_graphic": ("ui", "界面"),
}
COLOR_TERMS = {
    "blue": ("蓝", "blue"), "cyan": ("青", "cyan"), "red": ("红", "red"),
    "orange": ("橙", "orange"), "yellow": ("黄", "yellow"), "green": ("绿", "green"),
    "purple": ("紫", "purple"), "white": ("白", "white"), "black": ("黑", "black"),
}
FAMILY_TERMS = {
    "fire": ("火", "火焰", "fire"), "shield": ("盾", "护盾", "shield"),
    "lightning": ("雷", "电", "lightning", "thunder"), "ice": ("冰", "ice", "frost"),
    "explosion": ("爆炸", "爆发", "explosion"), "smoke": ("烟", "smoke"),
}
MOTION_TERMS = {
    "impact": ("冲击", "命中", "impact", "hit"), "flow": ("流动", "流光", "flow"),
    "pulse": ("脉冲", "pulse"), "dissolve": ("溶解", "消散", "dissolve"),
    "trail": ("拖尾", "trail"), "burst": ("爆发", "burst"),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _load_human_label_overlays(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path.resolve()):
        candidate_id = str(row.get("candidate_id") or "")
        label = row.get("human_label")
        eligibility = row.get("training_eligibility")
        if not candidate_id or not isinstance(label, dict) or not isinstance(eligibility, dict):
            raise ValueError(f"invalid human label overlay: {path}")
        if label.get("decision") == "not_visible":
            raise ValueError(f"not_visible label must not be supplied as a retrieval overlay: {candidate_id}")
        if eligibility.get("quality_supervision") is not True:
            raise ValueError(f"human overlay is not quality-supervision eligible: {candidate_id}")
        if candidate_id in result:
            raise ValueError(f"duplicate human label overlay candidate: {candidate_id}")
        result[candidate_id] = row
    return result


def _contains(text: str, values: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(value.lower() in lowered for value in values)


def parse_prompt(text: str, prompt_id: str, candidate_count: int, seed: int) -> dict[str, Any]:
    style = next((name for name, terms in STYLE_TERMS.items() if _contains(text, terms)), "unknown")
    colors = sorted(name for name, terms in COLOR_TERMS.items() if _contains(text, terms))
    families = sorted(name for name, terms in FAMILY_TERMS.items() if _contains(text, terms))
    motions = sorted(name for name, terms in MOTION_TERMS.items() if _contains(text, terms))
    categories = ["ui"] if style == "ui_graphic" else ["battle"]
    if _contains(text, ("角色", "character")):
        categories = ["character"]
    timing = "unknown"
    if _contains(text, ("快速", "瞬间", "短促", "fast", "quick")):
        timing = "fast_impact"
    elif _contains(text, ("循环", "持续", "loop")):
        timing = "loop"
    elif _contains(text, ("长", "long")):
        timing = "long"
    elif _contains(text, ("短", "short")):
        timing = "short"
    negative = []
    for match in re.findall(r"(?:不要|避免|禁止|without|no)\s*([^，,。.;]+)", text, flags=re.IGNORECASE):
        if match.strip():
            negative.append(match.strip())
    result = {
        "schema_version": "vfx_prompt_condition.v1", "prompt_id": prompt_id, "text": text,
        "style_family": style, "color_keywords": colors, "effect_families": families,
        "source_categories": categories, "motion_keywords": motions, "timing_profile": timing,
        "negative_constraints": sorted(set(negative)), "candidate_count": candidate_count, "seed": seed,
    }
    schema = _read_json(Path("workspace/data/vfx_generation/schemas/vfx_prompt_condition.schema.json"))
    errors = list(Draft202012Validator(schema).iter_errors(result))
    if errors:
        raise ValueError(errors[0].message)
    return result


def _trajectory_preferences(prompt: dict[str, Any]) -> list[str]:
    motions = set(prompt["motion_keywords"])
    result = []
    if motions & {"impact", "burst", "pulse"}:
        result.extend(("emission_alpha", "mpb", "texture_swap"))
    if "dissolve" in motions:
        result.append("dissolve")
    if motions & {"flow", "trail"}:
        result.append("flow_distortion")
    return result or ["emission_alpha", "flow_distortion", "mpb"]


def _prefab_material_paths(row: dict[str, Any]) -> set[str]:
    selection = row["inputs"].get("material_selection") or {}
    materials = selection.get("materials") or []
    return {
        str(material["material_path"])
        for material in materials
        if isinstance(material, dict) and material.get("material_path")
    }


def _trajectory_material_paths(row: dict[str, Any]) -> set[str]:
    selection = row["inputs"].get("material_selection") or {}
    materials = selection.get("materials") or []
    return {
        str(material["material_path"])
        for material in materials
        if isinstance(material, dict) and material.get("material_path")
    }


def _prefab_score(
    row: dict[str, Any],
    prompt: dict[str, Any],
    human_overlay: dict[str, Any] | None = None,
) -> tuple[float, list[str], list[str], dict[str, Any] | None]:
    score, reasons = 0.0, []
    categories = set(row["inputs"]["source_category"])
    if categories.intersection(prompt["source_categories"]):
        score += 3.0; reasons.append("source_category_match")
    family = row["inputs"]["effect_family_hint"]
    if family in prompt["effect_families"]:
        score += 5.0; reasons.append("effect_family_match")
    evidence = row["outputs"]["render_evidence"]
    if evidence["status"] == "pass":
        score += 1.0; reasons.append("auto_eval_pass")
    score += min(2.0, float(evidence["metrics"].get("visible_area_ratio_peak") or 0.0) * 12.0)
    score += min(2.0, float(evidence["metrics"].get("frame_delta_mean") or 0.0) * 120.0)
    duration = float(row["outputs"]["prefab_summary"].get("estimated_duration_seconds") or 0.0)
    if prompt["timing_profile"] == "fast_impact" and duration <= 2.0:
        score += 1.5; reasons.append("fast_duration_match")
    if prompt["timing_profile"] == "loop" and row["outputs"]["prefab_summary"].get("looping"):
        score += 1.5; reasons.append("loop_match")
    unmatched = []
    label_context = None
    human_label = human_overlay.get("human_label") if isinstance(human_overlay, dict) else None
    if isinstance(human_label, dict):
        decision = str(human_label.get("decision") or "")
        quality = int(human_label.get("quality_score") or 0)
        style = str(human_label.get("style_family") or "unknown")
        if decision == "accept_reference":
            score += 3.0; reasons.append("human_accept_reference")
        elif decision == "partial":
            score += 1.0; reasons.append("human_partial_reuse")
        elif decision == "reject":
            score -= 4.0; reasons.append("human_reject_penalty")
        score += (quality - 3) * 0.35
        if prompt["style_family"] != "unknown":
            if style == prompt["style_family"]:
                score += 4.0; reasons.append("human_style_match")
            elif style != "unknown":
                score -= 1.5; reasons.append("human_style_mismatch")
            else:
                unmatched.append("style_human_label_unknown")
        label_context = {
            "decision": decision,
            "style_family": style,
            "quality_score": quality,
            "reviewed_at": human_overlay.get("reviewed_at"),
            "confirmation_mode": human_label.get("confirmation_mode"),
        }
    elif prompt["style_family"] != "unknown":
        unmatched.append("style_requires_human_labels")
    if prompt["color_keywords"]: unmatched.append("color_not_yet_scored")
    if prompt["effect_families"] and family not in prompt["effect_families"]: unmatched.append("effect_family_not_matched")
    return score, reasons, unmatched, label_context


def retrieve_candidates(
    prompt: dict[str, Any],
    prefab_rows: list[dict[str, Any]],
    material_rows: list[dict[str, Any]],
    human_overlays: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    human_overlays = human_overlays or {}
    scored = []
    for row in prefab_rows:
        overlay = human_overlays.get(str(row["candidate_id"]))
        score, reasons, unmatched, label_context = _prefab_score(row, prompt, overlay)
        tie = hashlib.sha256(f"{prompt['seed']}:{row['candidate_id']}".encode()).hexdigest()
        scored.append((score, tie, row, reasons, unmatched, label_context))
    scored.sort(key=lambda value: (-value[0], value[1]))
    preferred = _trajectory_preferences(prompt)
    trajectories = [
        row for row in material_rows
        if row["split"]["name"] == "train" and row["label"]["trajectory_label"] == "positive"
    ]

    # A trajectory controls a concrete source material. It cannot be applied to an
    # unrelated Prefab and still be called a valid composition candidate.
    compatible_pairs = []
    for score, _, prefab, reasons, unmatched, label_context in scored:
        prefab_materials = _prefab_material_paths(prefab)
        for trajectory in trajectories:
            shared_materials = sorted(prefab_materials.intersection(_trajectory_material_paths(trajectory)))
            if not shared_materials:
                continue
            category = trajectory["inputs"]["trajectory_category"]
            category_rank = preferred.index(category) if category in preferred else len(preferred)
            tie = hashlib.sha256(
                f"{prompt['seed']}:{prefab['candidate_id']}:{trajectory['candidate_id']}".encode()
            ).hexdigest()
            compatible_pairs.append((
                score + (len(preferred) - category_rank) * 0.1,
                category_rank,
                tie,
                prefab,
                trajectory,
                shared_materials,
                reasons,
                unmatched,
                label_context,
            ))

    compatible_pairs.sort(key=lambda value: (-value[0], value[1], value[2]))
    selected_pairs = []
    selected_prefabs: set[str] = set()
    for pair in compatible_pairs:
        prefab_id = str(pair[3]["candidate_id"])
        if prefab_id in selected_prefabs:
            continue
        selected_pairs.append(pair)
        selected_prefabs.add(prefab_id)
        if len(selected_pairs) == prompt["candidate_count"]:
            break
    if len(selected_pairs) < prompt["candidate_count"]:
        for pair in compatible_pairs:
            if pair in selected_pairs:
                continue
            selected_pairs.append(pair)
            if len(selected_pairs) == prompt["candidate_count"]:
                break
    if len(selected_pairs) < prompt["candidate_count"]:
        raise ValueError(
            "not enough direct Prefab-material trajectory bindings "
            f"(need {prompt['candidate_count']}, found {len(selected_pairs)})"
        )

    candidates = []
    for index, (score, _, _, prefab, trajectory, shared_materials, reasons, unmatched, label_context) in enumerate(selected_pairs, start=1):
        frame_paths = prefab["outputs"]["render_paths"]
        representative = max(frame_paths, key=lambda value: Path(value).stat().st_size)
        candidates.append({
            "candidate_id": f"{prompt['prompt_id']}_c{index:03d}", "seed": prompt["seed"] + index,
            "source_prefab": {"case_id": prefab["candidate_id"], "prefab_path": prefab["inputs"]["prefab_path"], "source_category": prefab["inputs"]["source_category"], "effect_family_hint": prefab["inputs"]["effect_family_hint"]},
            "material_trajectory": {"trajectory_id": trajectory["candidate_id"], "spec_path": trajectory["inputs"]["spec_path"], "category": trajectory["inputs"]["trajectory_category"], "control_scope": trajectory["inputs"]["control_scope"], "material_paths": shared_materials, "binding_status": "direct_prefab_renderer_material"},
            "selection_score": round(score, 6), "selection_reasons": reasons + ["direct_prefab_material_binding"], "unmatched_conditions": unmatched,
            "human_label_context": label_context,
            "evidence": {"representative_frame": representative, "render_paths": frame_paths, "auto_eval": prefab["outputs"]["render_evidence"], "prefab_summary": prefab["outputs"]["prefab_summary"]},
            "execution_status": "retrieval_proposal_not_yet_composed",
        })
    return candidates


def _contact_sheet(candidates: list[dict[str, Any]], output: Path) -> Path:
    width, row_height = 1280, 220
    canvas = Image.new("RGB", (width, row_height * len(candidates)), "#10151b")
    draw, font = ImageDraw.Draw(canvas), ImageFont.load_default()
    for index, candidate in enumerate(candidates):
        top = index * row_height
        with Image.open(candidate["evidence"]["representative_frame"]) as image:
            preview = image.convert("RGB"); preview.thumbnail((300, 190)); canvas.paste(preview, (15, top + 15))
        lines = [candidate["candidate_id"], Path(candidate["source_prefab"]["prefab_path"]).name, f"trajectory={candidate['material_trajectory']['trajectory_id']}", f"score={candidate['selection_score']}", "reasons=" + ", ".join(candidate["selection_reasons"]), "unmatched=" + ", ".join(candidate["unmatched_conditions"])]
        draw.multiline_text((335, top + 18), "\n".join(lines), fill="white", font=font, spacing=6)
    output.parent.mkdir(parents=True, exist_ok=True); canvas.save(output, quality=90); return output


def build_retrieval_run(
    prompt: dict[str, Any],
    prefab_dataset: Path,
    material_dataset: Path,
    output_root: Path,
    run_id: str,
    human_label_overlays: Path | None = None,
) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()): raise FileExistsError(output_root)
    prefabs = _read_jsonl(prefab_dataset / "image_feature_examples.jsonl")
    materials = _read_jsonl(material_dataset / "material_state_examples.jsonl")
    overlays = _load_human_label_overlays(human_label_overlays)
    matched_overlay_count = sum(str(row["candidate_id"]) in overlays for row in prefabs)
    candidates = retrieve_candidates(prompt, prefabs, materials, overlays)
    selected_overlay_count = sum(row["human_label_context"] is not None for row in candidates)
    human_assisted = matched_overlay_count > 0
    limitations = [
        "Candidates use direct Prefab-to-material bindings and are not yet composed or re-executed in Unity.",
        "Color conditions remain unscored until color semantics are independently annotated.",
        "Selection score is a retrieval heuristic, not final aesthetic acceptance.",
    ]
    if not human_assisted:
        limitations.append("Style conditions remain unscored until human labels are available.")
    else:
        limitations.append("Human style and quality labels affect only matching reviewed Prefabs; unreviewed and technical-exclusion Prefabs do not receive inferred quality labels.")
    manifest = {
        "schema_version":"prompt_retrieval_manifest.v1",
        "created_at":datetime.now(timezone.utc).isoformat(),
        "run_id":run_id,
        "prompt_condition":prompt,
        "candidate_count":len(candidates),
        "candidates":candidates,
        "human_aesthetic_labels_used":matched_overlay_count,
        "human_aesthetic_labels_selected":selected_overlay_count,
        "human_label_overlay_path":human_label_overlays.resolve().as_posix() if human_label_overlays else None,
        "status":"retrieval_human_label_assisted" if human_assisted else "retrieval_baseline",
        "limitations":limitations,
    }
    schema = _read_json(Path("workspace/data/vfx_generation/schemas/prompt_retrieval_manifest.schema.json")); errors=list(Draft202012Validator(schema).iter_errors(manifest))
    if errors: raise ValueError(errors[0].message)
    manifest_path=_write_json(output_root/"retrieval_manifest.json",manifest); prompt_path=_write_json(output_root/"prompt_condition.json",prompt); sheet=_contact_sheet(candidates,output_root/"contact_sheet.jpg")
    return {"manifest":manifest_path,"prompt":prompt_path,"contact_sheet":sheet}


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--prompt",required=True); parser.add_argument("--prompt-id",required=True); parser.add_argument("--prefab-dataset",type=Path,required=True); parser.add_argument("--material-dataset",type=Path,required=True); parser.add_argument("--output-root",type=Path,required=True); parser.add_argument("--run-id",required=True); parser.add_argument("--count",type=int,default=6); parser.add_argument("--seed",type=int,default=20260828); parser.add_argument("--human-label-overlays",type=Path); args=parser.parse_args(argv)
    try:
        prompt=parse_prompt(args.prompt,args.prompt_id,args.count,args.seed); paths=build_retrieval_run(prompt,args.prefab_dataset,args.material_dataset,args.output_root,args.run_id,args.human_label_overlays)
    except (OSError,ValueError,FileExistsError,json.JSONDecodeError) as error:
        print(json.dumps({"success":False,"error":str(error)},ensure_ascii=False)); return 2
    print(json.dumps({"success":True,**{k:v.as_posix() for k,v in paths.items()}},ensure_ascii=False,indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
