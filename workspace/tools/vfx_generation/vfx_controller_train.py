"""Training preflight for the future MiniMind-compatible VFX Controller."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TrainingNotReady(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_preflight(dataset_manifest: Path, *, minimum_sft_examples: int, minimum_sft_families: int) -> dict[str, Any]:
    manifest = _read_json(dataset_manifest.resolve())
    gate = manifest.get("training_gate") if isinstance(manifest.get("training_gate"), dict) else {}
    sft_count = int(manifest.get("sft_example_count") or 0)
    families = manifest.get("sft_family_counts") if isinstance(manifest.get("sft_family_counts"), dict) else manifest.get("family_counts")
    if not isinstance(families, dict):
        families = {}
    family_count = len([key for key, value in families.items() if int(value) > 0 and key != "unknown"])
    reasons = []
    if gate.get("status") != "ready":
        reasons.append(str(gate.get("reason") or "dataset training gate is not ready"))
    if sft_count < minimum_sft_examples:
        reasons.append(f"need at least {minimum_sft_examples} positive SFT examples; found {sft_count}")
    if family_count < minimum_sft_families:
        reasons.append(f"need at least {minimum_sft_families} labeled effect families; found {family_count}")
    return {
        "schema_version": "vfx_controller_training_preflight.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_manifest": dataset_manifest.resolve().as_posix(),
        "backend": "minimind_controller_adapter",
        "sft_example_count": sft_count,
        "labeled_family_count": family_count,
        "minimum_sft_examples": minimum_sft_examples,
        "minimum_sft_families": minimum_sft_families,
        "status": "ready" if not reasons else "blocked_insufficient_labels",
        "reasons": reasons,
        "weight_written": False,
        "policy": {
            "not_visible_is_not_training_data": True,
            "technical_pass_is_not_aesthetic_acceptance": True,
            "controller_does_not_generate_unverified_unity_assets": True,
        },
    }


def audit(dataset_manifest: Path, output: Path, *, minimum_sft_examples: int, minimum_sft_families: int) -> Path:
    return _write_json(output.resolve(), build_preflight(dataset_manifest, minimum_sft_examples=minimum_sft_examples, minimum_sft_families=minimum_sft_families))


def train(dataset_manifest: Path, output_dir: Path, *, minimum_sft_examples: int, minimum_sft_families: int) -> Path:
    preflight = build_preflight(dataset_manifest, minimum_sft_examples=minimum_sft_examples, minimum_sft_families=minimum_sft_families)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = _write_json(output_dir / "training_preflight.json", preflight)
    if preflight["status"] != "ready":
        raise TrainingNotReady(f"Controller training refused: {'; '.join(preflight['reasons'])}. No model weight was written.")
    plan = {
        "schema_version": "vfx_controller_training_plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "minimind_controller_adapter",
        "dataset_manifest": dataset_manifest.resolve().as_posix(),
        "sft_path": str((dataset_manifest.resolve().parent / "minimind_sft.jsonl").resolve()),
        "status": "ready_for_backend_execution",
        "weight_written": False,
        "next_step": "invoke a pinned MiniMind-compatible backend after model and tokenizer paths are configured",
    }
    _write_json(output_dir / "training_plan.json", plan)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit or preflight VFX Controller training readiness.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("audit", "train"):
        command = commands.add_parser(name)
        command.add_argument("--dataset-manifest", type=Path, required=True)
        command.add_argument("--minimum-sft-examples", type=int, default=32)
        command.add_argument("--minimum-sft-families", type=int, default=2)
        if name == "audit":
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            path = audit(args.dataset_manifest, args.output, minimum_sft_examples=args.minimum_sft_examples, minimum_sft_families=args.minimum_sft_families)
        else:
            path = train(args.dataset_manifest, args.output_dir, minimum_sft_examples=args.minimum_sft_examples, minimum_sft_families=args.minimum_sft_families)
    except TrainingNotReady as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "path": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
