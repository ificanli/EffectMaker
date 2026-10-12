"""Build a run-specific style and technical review queue from rendered VFX candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_style_review_queue(run_root: Path, output_path: Path) -> Path:
    run_root = run_root.resolve()
    manifest = _load_json(run_root / "run_manifest.json")
    rows: list[dict[str, Any]] = []
    for candidate in manifest.get("candidates", []):
        spec_path = run_root / str(candidate["spec_path"])
        spec = _load_json(spec_path)
        status = str(candidate.get("auto_eval", {}).get("status") or "unknown")
        task = "style_review" if status in {"pass", "warn"} else "technical_reject_review"
        source_layer = next((layer for layer in spec.get("layers", []) if layer.get("role") == "source_prefab"), {})
        rows.append(
            {
                "schema_version": "vfx_style_review_item.v1",
                "run_id": manifest["run_id"],
                "candidate_id": candidate["candidate_id"],
                "case_id": spec.get("training_case_id"),
                "prefab_path": source_layer.get("shape_parameters", {}).get("source_prefab_path"),
                "review_task": task,
                "auto_eval_status": status,
                "auto_eval_reasons": candidate.get("auto_eval", {}).get("hard_reject_reasons", []),
                "auto_eval_notes": candidate.get("auto_eval", {}).get("notes"),
                "target_style_profile": spec.get("target_style_profile"),
                "observed_style_profile": spec.get("observed_style_profile"),
                "render_manifest_path": candidate.get("render_manifest_path"),
                "capture_root": candidate.get("capture_root"),
                "render_frames": candidate.get("frames", []),
                "contact_sheet_page": candidate.get("contact_sheet_page"),
                "contact_sheet_row": candidate.get("contact_sheet_row"),
                "annotation": {
                    "status": "pending",
                    "style_family": None,
                    "style_keywords": [],
                    "style_axes": {},
                    "style_match_decision": "unlabeled",
                    "style_mismatch_dimensions": [],
                    "summary": None,
                },
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a VFX style review queue from a rendered run.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.run_root / "style_review_queue.jsonl"
    path = build_style_review_queue(args.run_root, output)
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
