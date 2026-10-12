"""Convert course evidence into traceable VFX priors without inventing training labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


RECORD_TYPES = ("tutorial_fact", "engineering_mapping", "unverified_assumption", "context")
FAMILIES = ("slash", "fire", "lightning", "shield", "smoke", "explosion", "magic_circle", "water", "unknown")
FAMILY_TERMS = {
    "slash": ("刀光", "弧线", "blade", "slash"),
    "fire": ("火焰", "烟花", "火星", "flame", "fire"),
    "lightning": ("雷电", "闪电", "雷之呼吸", "lightning", "thunder"),
    "shield": ("护盾", "屏障", "shield"),
    "smoke": ("烟雾", "烟火", "烟尘", "smoke"),
    "explosion": ("爆炸", "冲击波", "爆发", "explosion"),
    "magic_circle": ("法阵", "符文", "magic circle"),
    "water": ("水系", "水柱", "浪花", "water"),
}
SPECIALIZED_METRICS = {
    "slash": ["sharpness", "attack_direction", "width_profile", "tip_quality", "residual_flow"],
    "fire": ["turbulence", "root_brightness", "edge_breakup", "heat_layering"],
    "lightning": ["branch_readability", "instant_peak", "path_energy", "randomness_control"],
    "shield": ["wrap_volume", "impact_response", "surface_readability", "transparent_sorting"],
    "smoke": ["volume_feel", "soft_edge", "occlusion_balance", "dissipation_quality"],
    "explosion": ["impact_peak", "scale_readability", "inner_outer_layering", "residual_direction"],
    "magic_circle": ["symbol_density", "ground_attachment", "reveal_timing", "layer_clarity"],
    "water": ["flow_direction", "transparency_layering", "foam_edge", "gravity_return"],
}


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    root = _repo_root().resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _input_files(inputs: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for raw in inputs:
        path = raw.resolve()
        if not path.exists():
            raise FileNotFoundError(f"course input does not exist: {path}")
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".srt"}:
            found.add(path)
        elif path.is_dir():
            found.update(candidate.resolve() for candidate in path.rglob("*") if candidate.is_file() and candidate.suffix.lower() in {".md", ".txt", ".srt"})
    return sorted(found, key=lambda item: item.as_posix().casefold())


def _split_markdown(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    chunks: list[dict[str, Any]] = []
    heading = path.stem
    body: list[str] = []
    start_line = 1

    def flush(end_line: int) -> None:
        nonlocal body, start_line
        text = "\n".join(body).strip()
        if text:
            chunks.append({"heading": heading, "text": text, "start_line": start_line, "end_line": end_line})
        body = []
        start_line = end_line + 1

    for number, line in enumerate(lines, start=1):
        if line.startswith("#"):
            flush(number - 1)
            heading = line.lstrip("# ").strip() or path.stem
            start_line = number
        else:
            body.append(line)
    flush(len(lines))
    return chunks


def _record_type(text: str) -> str:
    lowered = text.casefold()
    if any(term in lowered for term in ("unverified_assumption", "unverified assumption", "待验证", "未验证", "不能确认", "不确定", "unknown", "尚未开始", "pending", "blocked")):
        return "unverified_assumption"
    if any(term in text for term in ("教程事实", "高置信教程事实", "tutorial_fact")):
        return "tutorial_fact"
    if any(term in text for term in ("工程映射", "engineering_mapping", "Unity实验", "复现", "制作步骤", "参数")):
        return "engineering_mapping"
    return "context"


def _status(text: str, record_type: str) -> str:
    if record_type == "unverified_assumption":
        return "unverified"
    negative_verification = re.search(
        r"(?:不能|不得|未|尚未|没有|不具备|无法|不是|并非|不等于|不允许)[^\n。]{0,60}"
        r"(?:已验证|验证完成|通过|verified)"
        r"|(?:已验证|验证完成|通过|verified)[^\n。]{0,60}(?:不能|不得|未|尚未|没有|无法|不是|并非|不等于|pending|partial)",
        text,
        flags=re.IGNORECASE,
    )
    if negative_verification or re.search(r"(?:尚未|仍未|未)完成[^\n。]{0,30}(?:复现|验证|映射|确认)", text):
        return "pending"
    negative_verified = re.search(
        r"(?:不能|不得|未|尚未|没有|不具备|无法|not|never)[^\n]{0,50}\bverified\b"
        r"|\bverified\b[^\n]{0,50}(?:不能|不得|未|尚未|没有|无法|pending|partial)",
        text,
        flags=re.IGNORECASE,
    )
    if negative_verified:
        return "pending"
    if re.search(r"(?:状态|结论|status|result)[^\n]{0,80}\bverified\b", text, flags=re.IGNORECASE):
        return "verified"
    if any(term in text for term in ("已验证", "真实创建、保存、读取并通过")):
        return "verified"
    if any(term in text for term in ("未完成", "尚未", "pending", "blocked", "待复核")):
        return "pending"
    return "unlabeled"


def _family(path: Path, text: str) -> str:
    haystack = f"{path.as_posix()}\n{text}".casefold()
    for family, terms in FAMILY_TERMS.items():
        if any(term.casefold() in haystack for term in terms):
            return family
    return "unknown"


def _evidence_level(text: str) -> str:
    if any(term in text for term in ("证据等级：高", "证据等级: 高", "高置信", "直接证据")):
        return "high"
    if any(term in text for term in ("证据等级：中", "证据等级: 中", "中高")):
        return "medium"
    return "low_or_unknown"


def _timecodes(text: str) -> list[str]:
    return sorted(set(re.findall(r"\b\d{1,3}:\d{2}(?::\d{2})?\s*[–-]\s*\d{1,3}:\d{2}(?::\d{2})?\b", text)))[:12]


def build_index(inputs: Iterable[Path], output_dir: Path, index_id: str) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"course index output already exists and is not empty: {output_dir}")
    files = _input_files(inputs)
    records: list[dict[str, Any]] = []
    for path in files:
        for chunk_index, chunk in enumerate(_split_markdown(path), start=1):
            text = str(chunk["text"])
            record_type = _record_type(text)
            status = _status(text, record_type)
            family = _family(path, f"{chunk['heading']}\n{text}")
            record_id = hashlib.sha256(f"{index_id}|{path.as_posix()}|{chunk['start_line']}|{chunk_index}".encode("utf-8")).hexdigest()[:20]
            records.append({
                "schema_version": "course_knowledge_record.v1",
                "record_id": record_id,
                "source_path": _portable(path),
                "heading": chunk["heading"],
                "line_start": chunk["start_line"],
                "line_end": chunk["end_line"],
                "excerpt": text[:1200],
                "record_type": record_type,
                "status": status,
                "effect_family": family,
                "evidence_level": _evidence_level(text),
                "timecodes": _timecodes(text),
                "eligible_for_vfxspec_prior": record_type in {"tutorial_fact", "engineering_mapping"} and status == "verified" and family != "unknown",
                "training_eligibility": {
                    "controller_sft": False,
                    "prompt_condition_supervision": False,
                    "positive_generation_supervision": False,
                    "preference_training": False,
                    "reason": "course knowledge requires Unity reproduction and human visual confirmation",
                },
            })
    records_path = _write_jsonl(output_dir / "course_knowledge_records.jsonl", records)
    manifest = {
        "schema_version": "course_knowledge_index.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_id": index_id,
        "input_count": len(files),
        "record_count": len(records),
        "record_type_counts": dict(sorted(Counter(row["record_type"] for row in records).items())),
        "status_counts": dict(sorted(Counter(row["status"] for row in records).items())),
        "files": {"records": records_path.name},
        "policy": {
            "source_text_is_evidence_not_training_label": True,
            "unverified_assumption_is_not_vfxspec_prior": True,
            "verified_course_fact_still_requires_unity_reproduction": True,
            "not_visible_is_not_training_data": True,
        },
        "status": "pass",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/course_knowledge_index.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise ValueError(f"course index manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "course_knowledge_index.json", manifest)
    return {"manifest": manifest_path, "records": records_path}


def _vfxspec_prior(record: dict[str, Any], index_id: str, ordinal: int) -> dict[str, Any]:
    family = str(record["effect_family"])
    candidate_id = f"course_{record['record_id']}"
    return {
        "schema_version": "vfxspec.v1",
        "effect_family": family,
        "effect_type": "course_engineering_prior",
        "prompt": str(record["heading"]),
        "negative_prompt": "未经Unity复现和人工确认，不得当作最终视觉结果",
        "adapter": {
            "name": f"{family}.adapter",
            "version": "course-prior-only",
            "generator_family": "course_knowledge_prior",
            "specialized_metrics": SPECIALIZED_METRICS.get(family, []),
        },
        "reference": {
            "source_id": index_id,
            "case_id": record["record_id"],
            "frames": [{"time_seconds": 0.0, "path": record["source_path"], "role": "course_evidence_excerpt"}],
        },
        "generation": {
            "run_id": f"course_knowledge_{index_id}",
            "candidate_id": candidate_id,
            "seed": int(hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:8], 16),
            "generator": "course_knowledge_adapter",
            "generator_version": "course_knowledge_adapter.v1",
            "parent_candidate_id": None,
        },
        "layers": [{
            "role": "course_engineering_prior",
            "status": "placeholder",
            "topology": "requires_family_adapter_mapping",
            "constraints": ["requires_unity_reproduction", "not_visual_acceptance", "not_positive_training"],
            "shape_parameters": {"source_record_id": record["record_id"], "evidence_level": record["evidence_level"]},
        }],
    }


def export_controller_candidates(index_path: Path, output_dir: Path, adapter_id: str) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"course adapter output already exists and is not empty: {output_dir}")
    index_path = index_path.resolve()
    index = _read_json(index_path)
    records_path = index_path.parent / str(index["files"]["records"])
    records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    priors: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    exclusion_counts: Counter[str] = Counter()
    for ordinal, record in enumerate(records, start=1):
        if not record.get("eligible_for_vfxspec_prior"):
            reason = "unverified_course_evidence" if record["record_type"] == "unverified_assumption" or record["status"] != "verified" else "unknown_effect_family"
            exclusion_counts[reason] += 1
            exclusions.append({"record_id": record["record_id"], "source_path": record["source_path"], "reason": reason, "training_eligibility": record["training_eligibility"]})
            continue
        spec = _vfxspec_prior(record, str(index.get("index_id") or adapter_id), ordinal)
        spec_path = output_dir / "vfxspec_priors" / f"{spec['generation']['candidate_id']}.json"
        _write_json(spec_path, spec)
        errors = list(Draft202012Validator(_read_json(_repo_root() / "workspace/data/vfx_generation/schemas/vfxspec.schema.json")).iter_errors(spec))
        if errors:
            raise ValueError(f"course VFXSpec schema error for {record['record_id']}: {errors[0].message}")
        priors.append({"record_id": record["record_id"], "vfxspec_path": _portable(spec_path), "effect_family": record["effect_family"], "status": "engineering_prior_only"})
        candidates.append({
            "schema_version": "course_controller_candidate.v1",
            "candidate_id": spec["generation"]["candidate_id"],
            "input": {"prompt": record["heading"], "course_evidence": record["excerpt"], "effect_family": record["effect_family"]},
            "target": {"kind": "vfxspec_prior", "vfxspec_path": _portable(spec_path)},
            "provenance": {"knowledge_index": _portable(index_path), "record_id": record["record_id"], "source_path": record["source_path"], "line_start": record["line_start"], "line_end": record["line_end"], "timecodes": record["timecodes"]},
            "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "excluded_reasons": ["course_prior_requires_unity_reproduction_and_human_confirmation"]},
        })
    priors_path = _write_jsonl(output_dir / "vfxspec_priors.jsonl", priors)
    candidates_path = _write_jsonl(output_dir / "controller_candidates.jsonl", candidates)
    exclusions_path = _write_jsonl(output_dir / "course_training_exclusions.jsonl", exclusions)
    manifest = {
        "schema_version": "course_controller_adapter.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter_id": adapter_id,
        "knowledge_record_count": len(records),
        "spec_prior_count": len(priors),
        "controller_candidate_count": len(candidates),
        "excluded_count": len(exclusions),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "files": {"vfxspec_priors": priors_path.name, "controller_candidates": candidates_path.name, "exclusions": exclusions_path.name},
        "training_policy": {
            "course_priors_are_not_visual_labels": True,
            "controller_sft_count": 0,
            "requires_unity_reproduction": True,
            "requires_human_prompt_condition_feedback": True,
            "unverified_assumption_is_excluded": True,
            "not_visible_is_not_training_data": True,
        },
        "status": "pass",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/course_controller_adapter.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise ValueError(f"course adapter manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "course_controller_adapter_manifest.json", manifest)
    return {"manifest": manifest_path, "priors": priors_path, "candidates": candidates_path, "exclusions": exclusions_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adapt course evidence into safe VFX Controller priors.")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index")
    index.add_argument("--input", type=Path, action="append", required=True)
    index.add_argument("--output-dir", type=Path, required=True)
    index.add_argument("--index-id", required=True)
    export = commands.add_parser("export")
    export.add_argument("--index", type=Path, required=True)
    export.add_argument("--output-dir", type=Path, required=True)
    export.add_argument("--adapter-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_index(args.input, args.output_dir, args.index_id) if args.command == "index" else export_controller_candidates(args.index, args.output_dir, args.adapter_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
