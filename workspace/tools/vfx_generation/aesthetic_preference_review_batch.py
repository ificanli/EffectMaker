"""Build pending human A/B preference batches from verified VFX variation runs."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


class PreferenceReviewBatchError(ValueError):
    """Raised when variation candidates are not safely comparable."""


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PreferenceReviewBatchError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    root = _repo_root().resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve(value: str, base: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _candidate_from_manifest(path: Path) -> dict[str, Any] | None:
    manifest = _read_json(path.resolve())
    if manifest.get("technical_status") != "pass":
        return None
    result_path = _resolve(str(manifest.get("execution_result_path") or ""), path.parent)
    proposal_path = _resolve(str(manifest.get("proposal_manifest") or ""), path.parent)
    if not result_path.is_file() or not proposal_path.is_file():
        raise FileNotFoundError(f"variation evidence is incomplete: {path}")
    result = _read_json(result_path)
    proposal = _read_json(proposal_path)
    frames: list[dict[str, Any]] = []
    for frame in result.get("frames", []):
        if not isinstance(frame, dict) or not frame.get("valid") or not isinstance(frame.get("path"), str):
            continue
        frame_path = result_path.parent / "frames" / str(frame["path"])
        if not frame_path.is_file():
            raise FileNotFoundError(f"variation frame is missing: {frame_path}")
        frames.append({"path": _portable(frame_path), "time_seconds": float(frame.get("requested_time_seconds") or 0.0)})
    if len(frames) < 2 or int(result.get("valid_frame_count") or 0) != len(frames):
        raise PreferenceReviewBatchError(f"variation has incomplete continuous frames: {path}")
    prompt = proposal.get("prompt_condition") if isinstance(proposal.get("prompt_condition"), dict) else {}
    source_prefab = proposal.get("source_prefab") if isinstance(proposal.get("source_prefab"), dict) else {}
    run_id = str(proposal.get("run_id") or path.parent.name)
    proposal_id = str(manifest.get("proposal_id") or proposal.get("proposal_id") or "")
    if not proposal_id:
        raise PreferenceReviewBatchError(f"variation proposal id is missing: {path}")
    unique_id = f"{proposal_id}__{run_id}"
    return {
        "candidate_id": unique_id,
        "source_candidate_id": proposal_id,
        "run_id": run_id,
        "prefab_path": str(source_prefab.get("prefab_path") or result.get("prefab_path") or ""),
        "spec_path": _portable(_resolve(str(result.get("spec_path") or ""), result_path.parent)),
        "frames": frames,
        "technical_status": "pass",
        "human_preference_status": "pending",
        "prompt": prompt,
        "source_manifest": _portable(path),
    }


def build_preference_review_batch(manifest_paths: Iterable[Path], output_dir: Path, batch_id: str, *, minimum_candidates: int = 4, maximum_candidates: int = 8) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"preference review output already exists and is not empty: {output_dir}")
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for raw_path in manifest_paths:
        path = raw_path.resolve()
        candidate = _candidate_from_manifest(path)
        if candidate is None:
            excluded.append({"source_manifest": _portable(path), "reason": "technical_status_not_pass"})
            continue
        candidates.append(candidate)
    if len(candidates) < minimum_candidates:
        raise PreferenceReviewBatchError(f"need at least {minimum_candidates} comparable technical-pass candidates; found {len(candidates)}")
    candidates.sort(key=lambda row: (row["run_id"], row["candidate_id"]))
    candidates = candidates[:maximum_candidates]
    prompts = {json.dumps(row["prompt"], ensure_ascii=False, sort_keys=True) for row in candidates}
    families = {str((row["prompt"].get("effect_families") or [""])[0]) for row in candidates}
    prefabs = {row["prefab_path"] for row in candidates}
    if len(prompts) != 1:
        raise PreferenceReviewBatchError("all preference candidates must use one identical prompt condition")
    if len(families) != 1 or not next(iter(families)):
        raise PreferenceReviewBatchError("all preference candidates must use one explicit effect family")
    prompt = json.loads(next(iter(prompts)))
    effect_family = next(iter(families))
    pairs = []
    for index, (left, right) in enumerate(itertools.combinations(candidates, 2), start=1):
        pair_seed = f"{batch_id}|{left['candidate_id']}|{right['candidate_id']}"
        pairs.append({
            "pair_id": "pair_" + hashlib.sha256(pair_seed.encode("utf-8")).hexdigest()[:16],
            "candidate_a": left["candidate_id"],
            "candidate_b": right["candidate_id"],
            "same_prompt": True,
            "same_effect_family": True,
            "same_prefab": left["prefab_path"] == right["prefab_path"],
            "preference": None,
            "reason_codes": [],
            "human_note": "",
            "status": "pending",
        })
    candidate_output = [
        {key: value for key, value in candidate.items() if key not in {"prompt", "source_manifest"}}
        for candidate in candidates
    ]
    batch = {
        "schema_version": "vfx_aesthetic_preference_review_batch.v1",
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "effect_family": effect_family,
        "candidate_count": len(candidate_output),
        "pair_count": len(pairs),
        "excluded_count": len(excluded),
        "candidates": candidate_output,
        "pairs": pairs,
        "status": "pending_human_preference",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/aesthetic_preference_review_batch.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(batch), key=lambda error: list(error.path))
    if errors:
        raise PreferenceReviewBatchError(f"preference review batch schema error: {errors[0].message}")
    batch_path = _write_json(output_dir / "preference_review_batch.json", batch)
    pairs_path = output_dir / "preference_pairs.jsonl"
    pairs_path.parent.mkdir(parents=True, exist_ok=True)
    pairs_path.write_text("".join(json.dumps({"batch_id": batch_id, **pair}, ensure_ascii=False, sort_keys=True) + "\n" for pair in pairs), encoding="utf-8")
    exclusions_path = output_dir / "technical_exclusions.jsonl"
    exclusions_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in excluded), encoding="utf-8")
    return {"batch": batch_path, "pairs": pairs_path, "exclusions": exclusions_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a pending human VFX A/B preference review batch.")
    parser.add_argument("--variant-manifest", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--minimum-candidates", type=int, default=4)
    parser.add_argument("--maximum-candidates", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        paths = build_preference_review_batch(args.variant_manifest, args.output_dir, args.batch_id, minimum_candidates=args.minimum_candidates, maximum_candidates=args.maximum_candidates)
    except (PreferenceReviewBatchError, FileNotFoundError, FileExistsError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
