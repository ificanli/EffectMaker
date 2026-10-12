"""Select a deterministic, diverse review batch from Prefab training cases."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _has_editor_bound_texture(case: dict[str, Any]) -> bool:
    materials = case.get("inputs", {}).get("material_selection", {}).get("materials", [])
    return any(int(material.get("editor_bound_texture_slot_count") or 0) > 0 for material in materials if isinstance(material, dict))


def _eligible(case: dict[str, Any], *, exclude_runtime_context: bool) -> bool:
    if case.get("training", {}).get("supervision_status") != "needs_render_and_style_annotation":
        return False
    health = case.get("observations", {}).get("dependency_health", {})
    if int(health.get("missing_dependency_count") or 0) > 0:
        return False
    if exclude_runtime_context and int(health.get("ignored_dependency_count") or 0) > 0:
        return False
    if int(case.get("inputs", {}).get("material_selection", {}).get("material_count") or 0) < 1:
        return False
    return _has_editor_bound_texture(case)


def _bucket_key(case: dict[str, Any]) -> tuple[str, str]:
    source = case.get("source", {})
    categories = source.get("source_category") or ["unclassified"]
    return str(categories[0]), str(source.get("effect_family_hint") or "unclassified")


def select_review_batch(
    cases_path: Path,
    output_path: Path,
    *,
    batch_id: str,
    count: int = 16,
    exclude_runtime_context: bool = True,
) -> Path:
    if count < 1:
        raise ValueError("count must be positive")
    candidates = [case for case in _load_jsonl(cases_path) if _eligible(case, exclude_runtime_context=exclude_runtime_context)]
    buckets: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(deque)
    for case in sorted(candidates, key=lambda item: str(item.get("case_id"))):
        buckets[_bucket_key(case)].append(case)
    ordered_keys = sorted(buckets, key=lambda key: (key[1] == "unclassified", key[0], key[1]))
    selected: list[dict[str, Any]] = []
    while len(selected) < count and any(buckets.values()):
        for key in ordered_keys:
            if buckets[key] and len(selected) < count:
                selected.append(buckets[key].popleft())
    if len(selected) < count:
        raise ValueError(f"only {len(selected)} eligible cases are available; requested {count}")

    records = []
    for case in selected:
        records.append(
            {
                "case_id": case["case_id"],
                "prefab_path": case["source"]["prefab_path"],
                "source_category": case["source"]["source_category"],
                "effect_family_hint": case["source"]["effect_family_hint"],
                "target_style_profile": case["inputs"]["target_style_profile"],
                "observed_style_profile": case["observations"]["observed_style_profile"],
                "material_selection": case["inputs"]["material_selection"],
                "dependency_health": case["observations"]["dependency_health"],
            }
        )
    payload = {
        "schema_version": "vfx_review_batch.v1",
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_cases_path": cases_path.resolve().as_posix(),
        "requested_count": count,
        "selected_count": len(records),
        "selection": {
            "supervision_status": "needs_render_and_style_annotation",
            "require_material": True,
            "require_editor_bound_texture": True,
            "exclude_source_missing": True,
            "exclude_runtime_context": exclude_runtime_context,
            "strategy": "round_robin_source_category_and_effect_family_hint",
        },
        "category_counts": dict(Counter(record["source_category"][0] for record in records)),
        "effect_family_hint_counts": dict(Counter(record["effect_family_hint"] for record in records)),
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select a deterministic VFX Prefab review batch.")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument("--include-runtime-context", action="store_true")
    args = parser.parse_args(argv)
    path = select_review_batch(
        args.cases,
        args.output,
        batch_id=args.batch_id,
        count=args.count,
        exclude_runtime_context=not args.include_runtime_context,
    )
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
