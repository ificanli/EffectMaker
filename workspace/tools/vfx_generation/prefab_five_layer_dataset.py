"""Assemble technical, visual, pseudo, human-gold and regression-gold Prefab records."""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from jsonschema import Draft202012Validator
from PIL import Image

from workspace.tools.vfx_generation.capture_visual_integrity import analyze_capture_manifest


RECORD_SCHEMA = "vfx_prefab_training_layer_record.v1"
DATASET_SCHEMA = "vfx_prefab_five_layer_dataset.v1"
TIERS = ("technical_corpus", "visual_feature_only", "ai_pseudo_label", "human_gold", "regression_gold")
PATH_FAMILY_TERMS = {
    "lightning": ("lightning", "thunder", "leidian", "rayline"),
    "explosion": ("explosion", "baozha", "boom"),
    "slash": ("slash", "daoguang", "blade", "zhan"),
    "fire": ("fire", "flame", "huoyan", "ranshao"),
    "shield": ("shield", "hudun", "sheilder"),
    "smoke": ("smoke", "yanwu"),
    "water": ("water", "shuibo", "splash"),
    "magic_circle": ("magiccircle", "magic_circle", "fazhen", "rune"),
    "ice": ("ice", "frost", "bing"),
}
ELEMENT_FAMILY_TERMS = {
    "lightning": ("lightning", "thunder", "leidian", "electric"),
    "fire": ("fire", "flame", "huoyan", "ranshao"),
    "smoke": ("smoke", "yanwu", "dust", "fog"),
    "water": ("water", "shuibo", "splash"),
    "ice": ("ice", "frost", "bing", "snow"),
}
EFFECT_TYPE_TERMS = {
    "slash": ("slash", "daoguang", "blade", "zhan", "sword"),
    "impact": ("impact", "hit", "burst", "strike"),
    "explosion": ("explosion", "baozha", "boom"),
    "magic_circle": ("magiccircle", "magic_circle", "fazhen", "rune"),
    "laser": ("laser", "beam"),
    "projectile": ("projectile", "missile", "bullet"),
    "muzzle": ("muzzle", "cast"),
    "shield": ("shield", "hudun"),
    "portal": ("portal",),
    "aura": ("aura", "charge"),
    "trail": ("trail", "tracer"),
    "area": ("warning", "telegraph", "aoe"),
    "environment": ("weather", "storm", "fireflies"),
}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _normalize_asset_path(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\\", "/").strip()
    marker = "/Assets/"
    if marker in text:
        text = "Assets/" + text.split(marker, 1)[1]
    return text or None


def _stable_id(prefix: str, *values: Any) -> str:
    payload = "|".join(str(value) for value in values)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split(prefab_group: str) -> str:
    bucket = int(hashlib.sha256(prefab_group.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def _source_case_index(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path.resolve()):
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        prefab_path = _normalize_asset_path(source.get("prefab_path") or row.get("prefab_path") or (row.get("inputs") or {}).get("prefab_path"))
        if prefab_path:
            result[prefab_path] = row
    return result


def _capture_index(roots: Iterable[Path]) -> dict[str, tuple[Path, dict[str, Any]]]:
    result: dict[str, tuple[Path, dict[str, Any]]] = {}
    for root in roots:
        for path in root.resolve().rglob("capture_manifest.json"):
            try:
                manifest = _read_json(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if manifest.get("capture_pipeline_version") != "play_mode_runtime_isolated_multiview.v2":
                continue
            prefab_path = _normalize_asset_path(manifest.get("effect"))
            if not prefab_path or prefab_path.startswith("__"):
                continue
            previous = result.get(prefab_path)
            if previous is None or str(manifest.get("created_at") or "") > str(previous[1].get("created_at") or ""):
                result[prefab_path] = (path, manifest)
    return result


def _resolve_capture_frame(manifest_path: Path, manifest: dict[str, Any], frame: dict[str, Any]) -> Path | None:
    root_text = manifest.get("capture_root")
    root = Path(str(root_text)) if root_text else manifest_path.parent
    if not root.is_absolute():
        root = manifest_path.parent / root
    value = frame.get("path")
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def _semantic_color(hue: float, saturation: float, value: float) -> str:
    if saturation < 0.16:
        return "white" if value > 0.7 else "gray"
    degrees = hue * 360.0
    if degrees < 15 or degrees >= 345:
        return "red"
    if degrees < 45:
        return "orange"
    if degrees < 70:
        return "yellow"
    if degrees < 165:
        return "green"
    if degrees < 200:
        return "cyan"
    if degrees < 260:
        return "blue"
    if degrees < 330:
        return "purple"
    return "red"


def _measure_colors(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    frames = [frame for frame in manifest.get("frames") or [] if frame.get("valid")]
    if not frames:
        return {"status": "not_available", "semantic_tags": [], "distribution": {}}
    selected = [frames[round(index * (len(frames) - 1) / max(1, min(5, len(frames) - 1)))] for index in range(min(6, len(frames)))]
    counts: Counter[str] = Counter()
    sampled = 0
    for frame in selected:
        path = _resolve_capture_frame(manifest_path, manifest, frame)
        if path is None or not path.is_file():
            continue
        with Image.open(path) as image:
            pixels = np.asarray(image.convert("RGB").resize((96, 96)), dtype=np.uint8)
        corners = np.concatenate((pixels[:5, :5].reshape(-1, 3), pixels[:5, -5:].reshape(-1, 3), pixels[-5:, :5].reshape(-1, 3), pixels[-5:, -5:].reshape(-1, 3)))
        background = np.median(corners, axis=0)
        visible = np.max(np.abs(pixels.astype(np.int16) - background.astype(np.int16)), axis=2) > 8
        for red, green, blue in pixels[visible][::4]:
            hue, saturation, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
            if value < 0.08:
                continue
            counts[_semantic_color(hue, saturation, value)] += 1
            sampled += 1
    distribution = {name: round(count / max(1, sampled), 6) for name, count in counts.most_common()}
    tags = [name for name, ratio in distribution.items() if ratio >= 0.08][:4]
    return {"status": "measured_visual", "semantic_tags": tags, "distribution": distribution, "sampled_pixel_count": sampled}


def _family_from_path(path: str | None) -> tuple[str | None, float]:
    lowered = (path or "").lower().replace("_", "")
    matches = [family for family, terms in PATH_FAMILY_TERMS.items() if any(term.replace("_", "") in lowered for term in terms)]
    return (matches[0], 0.45) if len(matches) == 1 else (None, 0.0)


def _tag_from_path(path: str | None, terms_by_tag: dict[str, tuple[str, ...]]) -> tuple[str | None, float]:
    lowered = (path or "").lower().replace("_", "")
    matches = [tag for tag, terms in terms_by_tag.items() if any(term.replace("_", "") in lowered for term in terms)]
    return (matches[0], 0.45) if len(matches) == 1 else (None, 0.0)


def _base_record(sample: dict[str, Any], tier: str, label_source: str, confidence: float | None, model_version: str | None) -> dict[str, Any]:
    now = _created_at()
    return {
        "schema_version": RECORD_SCHEMA,
        "record_id": _stable_id("layer", sample["sample_id"], tier, label_source, model_version or "none"),
        "sample_id": sample["sample_id"],
        "tier": tier,
        "source": sample["source"],
        "evidence": {"graph_path": sample.get("graph_path"), "capture_manifest_path": None, "material_timeline_path": None, "human_record_id": None, "parent_record_ids": []},
        "observations": {},
        "labels": {"target_effect_family": None, "effect_type": None, "target_color_tags": [], "observed_element_tags": [], "observed_color_tags": [], "quality_score": None, "scores": {}, "issues": [], "decision": None},
        "label_provenance": {"label_source": label_source, "confidence": confidence, "model_version": model_version, "reviewer": None, "parent_human_record_id": None, "distance": None, "created_at": now},
        "grouping": {"prefab_group": sample["prefab_group"], "source_group": sample["source_group"], "cluster_id": None, "prompt_group": None},
        "training": {"weight": 0.0, "eligible_tasks": [], "excluded_tasks": [], "split": sample["split"], "frozen": False, "expires_with_model_version": False},
        "status": "ready",
        "limitations": [],
    }


def _validate_record(validator: Draft202012Validator, record: dict[str, Any]) -> None:
    errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"five-layer record schema error at {location}: {errors[0].message}")


def assemble(
    graph_dataset_root: Path,
    output_root: Path,
    dataset_id: str,
    capture_roots: Iterable[Path] = (),
    source_cases_path: Path | None = None,
    judge_training_path: Path | None = None,
    judge_predictions_path: Path | None = None,
    human_gold_paths: Iterable[Path] = (),
) -> dict[str, Path]:
    graph_dataset_root = graph_dataset_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"five-layer output already exists and is not empty: {output_root}")
    graph_manifest = _read_json(graph_dataset_root / "dataset_manifest.json")
    graphs = _read_jsonl(graph_dataset_root / "graphs.jsonl")
    examples = _read_jsonl(graph_dataset_root / "examples.jsonl")
    example_by_graph = {row["graph_id"]: row for row in examples}
    source_cases = _source_case_index(source_cases_path)
    captures = _capture_index(capture_roots)
    record_validator = Draft202012Validator(_read_json(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_training_layer_record.schema.json"))
    active_human_rows = []
    active_human_by_prefab: dict[str, dict[str, Any]] = {}
    for human_gold_path in human_gold_paths:
        for row in _read_jsonl(human_gold_path.resolve()):
            if row.get("tier") != "human_gold" or row.get("label_provenance", {}).get("label_source") != "human":
                raise ValueError(f"active human input is not a verified human_gold record: {human_gold_path}")
            _validate_record(record_validator, row)
            prefab_path = _normalize_asset_path((row.get("source") or {}).get("prefab_path"))
            if not prefab_path or prefab_path in active_human_by_prefab:
                raise ValueError(f"active human input repeats or lacks Prefab path: {human_gold_path}")
            active_human_by_prefab[prefab_path] = row
            active_human_rows.append(row)
    samples: list[dict[str, Any]] = []
    sample_by_prefab: dict[str, dict[str, Any]] = {}
    for graph in graphs:
        example = example_by_graph[graph["graph_id"]]
        prefab_path = _normalize_asset_path((graph.get("source") or {}).get("prefab_path"))
        grouping = example.get("split_group") or {}
        prefab_group = str(grouping.get("prefab_group") or _stable_id("prefab", prefab_path or graph["graph_id"]))
        sample = {
            "sample_id": _stable_id("sample", graph["graph_id"]),
            "source": {"prefab_path": prefab_path, "graph_id": graph["graph_id"], "source_project": "UnityDemo/EffectDemo", "source_dataset_id": graph_manifest["dataset_id"]},
            "graph": graph,
            "graph_path": _portable(graph_dataset_root / "graphs.jsonl"),
            "prefab_group": prefab_group,
            "source_group": str(grouping.get("source_group") or "unknown_source"),
            "split": _split(prefab_group),
        }
        samples.append(sample)
        if prefab_path:
            sample_by_prefab[prefab_path] = sample

    records: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    visual_by_sample: dict[str, dict[str, Any]] = {}
    for sample in samples:
        graph = sample["graph"]
        prefab_path = sample["source"]["prefab_path"]
        source_case = source_cases.get(prefab_path or "", {})
        source_case_data = source_case.get("source") if isinstance(source_case.get("source"), dict) else source_case
        source_hint = str(source_case_data.get("effect_family_hint") or "unknown")
        technical = _base_record(sample, "technical_corpus", "none", None, None)
        technical["observations"] = {
            "source_hints": {"effect_family_hint": source_hint, "hint_source": "source_case_metadata" if source_case else "none"},
            "technical": {
                "node_count": len(graph["nodes"]),
                "particle_system_count": len(graph["components"]["particle_systems"]),
                "renderer_count": len(graph["components"]["renderers"]),
                "material_count": len(graph["asset_bindings"]["materials"]),
                "mesh_count": len(graph["asset_bindings"]["meshes"]),
                "reconstruction_status": graph["reconstruction"]["status"],
                "missing_fields": graph["reconstruction"]["missing_fields"],
                "unsupported_components": graph["reconstruction"]["unsupported_components"],
            },
        }
        technical["training"].update({"weight": 1.0, "eligible_tasks": list(graph["training"]["eligible_tasks"]), "excluded_tasks": sorted(set(graph["training"]["excluded_tasks"] + ["aesthetic_judge", "preference_training", "regression_evaluation"]))})
        _validate_record(record_validator, technical)
        records.append(technical)

        capture_entry = captures.get(prefab_path or "")
        if capture_entry:
            capture_path, capture = capture_entry
            visual_integrity = analyze_capture_manifest(capture_path, capture)
            if visual_integrity["material_render_error"]:
                exclusions.append({
                    "sample_id": sample["sample_id"],
                    "prefab_path": prefab_path,
                    "reason": visual_integrity["reason"],
                    "capture_manifest_path": _portable(capture_path),
                    "max_error_magenta_ratio": visual_integrity["max_error_magenta_ratio"],
                    "error_magenta_frame_count": visual_integrity["error_magenta_frame_count"],
                })
            elif capture.get("image_sequence_training_eligible") is True:
                colors = _measure_colors(capture_path, capture)
                visual = _base_record(sample, "visual_feature_only", "measured_visual", 1.0, "play_mode_runtime_isolated_multiview.v2")
                visual["evidence"].update({"capture_manifest_path": _portable(capture_path), "material_timeline_path": _portable(Path(str(capture.get("material_timeline_path")))) if capture.get("material_timeline_path") else None})
                frame_metrics = [frame.get("pixel_metrics") or {} for frame in capture.get("frames") or []]
                visual["observations"] = {
                    "visual": {
                        "capture_pipeline_version": capture.get("capture_pipeline_version"),
                        "frame_count": len(frame_metrics),
                        "duration_seconds": capture.get("duration_seconds"),
                        "selected_camera_view": (capture.get("camera_selection") or {}).get("selected_view"),
                        "max_visible_area_ratio": max((float(row.get("visible_area_ratio") or 0.0) for row in frame_metrics), default=0.0),
                        "cropped_frame_count": sum(bool(row.get("cropped")) for row in frame_metrics),
                        "visual_evidence_status": capture.get("visual_evidence_status"),
                        "material_render_integrity": "pass",
                        "max_error_magenta_ratio": visual_integrity["max_error_magenta_ratio"],
                    },
                    "measured_color": colors,
                }
                visual["training"].update({"weight": 1.0, "eligible_tasks": ["visual_self_supervision", "temporal_embedding", "clustering", "retrieval", "anomaly_detection"], "excluded_tasks": ["aesthetic_judge", "preference_training", "positive_generation_supervision"]})
                if capture.get("full_visual_training_eligible") is not True:
                    visual["limitations"].append("full_dynamic_material_fidelity_unavailable")
                _validate_record(record_validator, visual)
                records.append(visual)
                visual_by_sample[sample["sample_id"]] = visual
            else:
                exclusions.append({"sample_id": sample["sample_id"], "prefab_path": prefab_path, "reason": "capture_v2_image_sequence_ineligible", "capture_manifest_path": _portable(capture_path)})

        element_hint = source_hint if source_hint in ELEMENT_FAMILY_TERMS else None
        path_element, path_element_confidence = _tag_from_path(prefab_path, ELEMENT_FAMILY_TERMS)
        if element_hint is None:
            element_hint = path_element
        element_confidence = 0.62 if element_hint and element_hint == path_element and source_hint in ELEMENT_FAMILY_TERMS else 0.5 if source_hint in ELEMENT_FAMILY_TERMS else path_element_confidence
        source_type_hint = source_hint if source_hint in EFFECT_TYPE_TERMS else None
        path_type_hint, path_type_confidence = _tag_from_path(prefab_path, EFFECT_TYPE_TERMS)
        effect_type_hint = source_type_hint or path_type_hint
        effect_type_confidence = 0.62 if source_type_hint and source_type_hint == path_type_hint else 0.5 if source_type_hint else path_type_confidence
        color_tags = (visual_by_sample.get(sample["sample_id"], {}).get("observations", {}).get("measured_color", {}).get("semantic_tags") or [])
        if element_hint or effect_type_hint or color_tags:
            pseudo = _base_record(sample, "ai_pseudo_label", "ai_pseudo_label", max(element_confidence, effect_type_confidence, 0.65 if color_tags else 0.0), "weak_metadata_visual_teacher.v1")
            pseudo["evidence"]["parent_record_ids"] = [technical["record_id"]] + ([visual_by_sample[sample["sample_id"]]["record_id"]] if sample["sample_id"] in visual_by_sample else [])
            pseudo["labels"].update({"observed_element_tags": [element_hint] if element_hint else [], "observed_color_tags": sorted(set(color_tags)), "effect_type": effect_type_hint, "target_effect_family": effect_type_hint})
            pseudo["observations"] = {"source_hints": technical["observations"]["source_hints"], "measured_color": visual_by_sample.get(sample["sample_id"], {}).get("observations", {}).get("measured_color", {}), "inferred_effect_type": {"value": effect_type_hint, "confidence": effect_type_confidence, "source": "prefab_path"} if effect_type_hint else {"value": None, "confidence": 0.0, "source": "none"}}
            pseudo["training"].update({"weight": min(0.2, 0.2 * float(pseudo["label_provenance"]["confidence"] or 0.0)), "eligible_tasks": ["element_semisupervision", "type_semisupervision", "color_semisupervision", "active_learning_priority"], "excluded_tasks": ["human_gold", "regression_evaluation", "model_promotion", "preference_training"], "expires_with_model_version": True})
            _validate_record(record_validator, pseudo)
            records.append(pseudo)

    prediction_by_candidate = {}
    if judge_predictions_path and judge_predictions_path.is_file():
        prediction_payload = _read_json(judge_predictions_path.resolve())
        prediction_by_candidate = {str(row.get("candidate_id")): row for row in prediction_payload.get("predictions") or []}
    human_rows = _read_jsonl(judge_training_path.resolve()) if judge_training_path else []
    human_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in human_rows:
        prefab_path = _normalize_asset_path((row.get("provenance") or {}).get("prefab_path"))
        sample = sample_by_prefab.get(prefab_path or "")
        if sample:
            human_by_sample[sample["sample_id"]].append(row)
        else:
            exclusions.append({"candidate_id": row.get("candidate_id"), "prefab_path": prefab_path, "reason": "human_label_has_no_prefab_graph_sample"})
    sample_lookup = {sample["sample_id"]: sample for sample in samples}
    for sample_id, candidates in human_by_sample.items():
        candidates.sort(key=lambda row: str((row.get("label") or {}).get("reviewed_at") or row.get("record_id") or ""))
        row = candidates[-1]
        sample = sample_lookup[sample_id]
        if sample["source"]["prefab_path"] in active_human_by_prefab:
            continue
        has_v2 = sample_id in visual_by_sample
        gold = _base_record(sample, "human_gold", "human", 1.0, None)
        label = row.get("label") or {}
        gold["evidence"].update({"human_record_id": row.get("record_id"), "parent_record_ids": [str(item.get("record_id")) for item in candidates[:-1] if item.get("record_id")]})
        if has_v2:
            gold["evidence"]["capture_manifest_path"] = visual_by_sample[sample_id]["evidence"]["capture_manifest_path"]
        gold["labels"].update({"observed_element_tags": [str(row.get("effect_family"))] if row.get("effect_family") not in {None, "", "unknown", "unclassified"} else [], "observed_color_tags": [], "quality_score": label.get("quality_score"), "scores": label.get("scores") or {}, "issues": label.get("issues") or [], "decision": label.get("decision")})
        gold["label_provenance"].update({"reviewer": label.get("reviewer") or "local_human", "created_at": label.get("reviewed_at") or _created_at()})
        gold["training"].update({"weight": 1.0 if has_v2 else 0.75, "eligible_tasks": ["aesthetic_judge", "pseudo_label_calibration"] if has_v2 else ["aesthetic_judge_experimental"], "excluded_tasks": ["preference_training"] + ([] if has_v2 else ["regression_evaluation", "model_promotion"]), "split": sample["split"]})
        if not has_v2:
            gold["status"] = "pending_revalidation"
            gold["limitations"].append("pending_capture_v2_revalidation")
        prediction = prediction_by_candidate.get(str(row.get("candidate_id")))
        if prediction:
            gold["observations"]["ai_draft"] = prediction
        _validate_record(record_validator, gold)
        records.append(gold)

    for row in active_human_rows:
        prefab_path = _normalize_asset_path((row.get("source") or {}).get("prefab_path"))
        sample = sample_by_prefab.get(prefab_path or "")
        if sample is None or str(row.get("sample_id")) != str(sample["sample_id"]):
            raise ValueError(f"active human input does not match graph dataset sample: {prefab_path}")
        records.append(row)

    record_ids = [row["record_id"] for row in records]
    sample_tiers = [(row["sample_id"], row["tier"]) for row in records]
    ai_in_human = sum(row["tier"] == "human_gold" and row["label_provenance"]["label_source"] != "human" for row in records)
    regression_trainable = sum(row["tier"] == "regression_gold" and (row["training"]["weight"] > 0 or row["training"]["eligible_tasks"]) for row in records)
    paths = {
        "records": output_root / "records.jsonl",
        "technical": output_root / "technical_corpus.jsonl",
        "visual": output_root / "visual_feature_only.jsonl",
        "pseudo": output_root / "ai_pseudo_label.jsonl",
        "human_gold": output_root / "human_gold.jsonl",
        "regression_gold": output_root / "regression_gold.jsonl",
        "exclusions": output_root / "exclusions.jsonl",
    }
    records.sort(key=lambda row: (row["sample_id"], TIERS.index(row["tier"]), row["record_id"]))
    _write_jsonl(paths["records"], records)
    for tier, key in (("technical_corpus", "technical"), ("visual_feature_only", "visual"), ("ai_pseudo_label", "pseudo"), ("human_gold", "human_gold"), ("regression_gold", "regression_gold")):
        _write_jsonl(paths[key], (row for row in records if row["tier"] == tier))
    _write_jsonl(paths["exclusions"], exclusions)
    tier_counts = Counter(row["tier"] for row in records)
    visual_ready = sum(row["tier"] == "visual_feature_only" and row["status"] == "ready" for row in records)
    manifest = {
        "schema_version": DATASET_SCHEMA,
        "created_at": _created_at(),
        "dataset_id": dataset_id,
        "source_dataset_ids": sorted({graph_manifest["dataset_id"], "aesthetic_training_r006" if judge_training_path else "no_human_source", "prefab_active_review" if active_human_rows else "no_active_review_source"}),
        "sample_count": len(samples),
        "record_count": len(records),
        "tier_counts": {tier: tier_counts.get(tier, 0) for tier in TIERS},
        "status_counts": dict(sorted(Counter(row["status"] for row in records).items())),
        "files": {key: _portable(path) for key, path in paths.items()},
        "quality_gates": {"schema_errors": 0, "duplicate_record_ids": len(record_ids) - len(set(record_ids)), "duplicate_sample_tiers": len(sample_tiers) - len(set(sample_tiers)), "ai_labels_in_human_gold": ai_in_human, "regression_records_trainable": regression_trainable, "technical_sample_coverage": tier_counts.get("technical_corpus", 0) / max(1, len(samples)), "human_labels_overwritten": 0},
        "human_budget": {"initial_review_rate": 0.06, "stable_review_rate": 0.01, "minimum_queue_size": 16, "current_recommended_count": min(visual_ready, max(16, int(math.ceil(visual_ready * 0.06)))) if visual_ready else 0},
        "status": "pass",
    }
    manifest_schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_five_layer_dataset.schema.json")
    errors = list(Draft202012Validator(manifest_schema).iter_errors(manifest))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"five-layer dataset schema error at {location}: {errors[0].message}")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {"manifest": manifest_path, **paths}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble the five-layer Prefab training dataset.")
    parser.add_argument("--graph-dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--capture-root", type=Path, action="append", default=[])
    parser.add_argument("--source-cases", type=Path)
    parser.add_argument("--judge-training", type=Path)
    parser.add_argument("--judge-predictions", type=Path)
    parser.add_argument("--human-gold", type=Path, action="append", default=[], help="Merge verified vfx_prefab_training_layer human_gold JSONL records, overriding older labels for the same Prefab.")
    args = parser.parse_args(argv)
    try:
        paths = assemble(args.graph_dataset_root, args.output_root, args.dataset_id, args.capture_root, args.source_cases, args.judge_training, args.judge_predictions, args.human_gold)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
