"""Train and apply the narrow slash contact-hit placement model."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from .professional_core_rule_model import CoreRuleRanker, _pair_splits
from .professional_slash_hit_teacher_reproduction import CONTACT_POSITION, ORTHOGRAPHIC_SIZE, _summary
from .professional_teacher_guided_generation import _single_role_component


DATASET_SCHEMA = "vfx_professional_slash_hit_rule_training.v1"
MODEL_SCHEMA = "vfx_professional_slash_hit_rule_ranker.v1"
MODEL_VERSION = "professional_slash_hit_rule_ranker_mlp.v1"
CAPTURE_PROTOCOL = "slash_hit_fixed_orthographic.v1"
FEATURE_NAMES = (
    "hit.contact_position_error",
    "hit.start_size",
    "hit.start_delay",
    "hit.lifetime",
    "visual.contact_peak_luminance",
    "visual.contact_mean_luminance",
    "visual.center_peak_luminance",
    "visual.active_contact_frame_count",
)


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _features(graph: dict[str, Any], capture_manifest: Path) -> dict[str, float]:
    hit_node = next(node for node in graph["nodes"] if node.get("role") == "hit")
    hit = _single_role_component(graph, "particle_systems", "hit")["parameters"]
    position = [float(value) for value in hit_node["transform"]["local_position"]]
    visual = _summary(capture_manifest.resolve())["frames"]
    return {
        "hit.contact_position_error": sum((position[index] - float(CONTACT_POSITION[index])) ** 2 for index in range(3)) ** 0.5,
        "hit.start_size": float(hit["start_size_max"]),
        "hit.start_delay": float(hit["start_delay_max"]),
        "hit.lifetime": float(hit["start_lifetime_max"]),
        "visual.contact_peak_luminance": max((float(row["contact_peak_luminance"]) for row in visual), default=0.0),
        "visual.contact_mean_luminance": max((float(row["contact_luminance"]) for row in visual), default=0.0),
        "visual.center_peak_luminance": max((float(row["center_peak_luminance"]) for row in visual), default=0.0),
        "visual.active_contact_frame_count": float(sum(float(row["contact_luminance"]) >= 0.01 for row in visual)),
    }


def feature_vector(row: dict[str, Any]) -> list[float]:
    values = row.get("features") or {}
    return [float(values.get(name) or 0.0) for name in FEATURE_NAMES]


def build_dataset(manifest_path: Path, report_path: Path, output_root: Path, dataset_id: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"slash hit dataset output already exists and is not empty: {output_root}")
    manifest, report = _read_json(manifest_path.resolve()), _read_json(report_path.resolve())
    if report.get("status") != "pass":
        raise ValueError("passing slash hit ablation report is required")
    passing = {row["candidate_id"] for row in report["records"] if row["professional_rule_transfer_pass"]}
    split_by_pair = _pair_splits([row["candidate_id"] for row in manifest["candidates"] if row["candidate_id"] in passing])
    rows = []
    for candidate in manifest["candidates"]:
        pair_id = candidate["candidate_id"]
        if pair_id not in split_by_pair:
            continue
        variants = (
            (0, "center_misplaced", _resolve(candidate["baseline_graph_path"]), _resolve(candidate["baseline_capture_manifest_path"])),
            (1, "contact_aligned", _resolve(candidate["guided_graph_path"]), _resolve(candidate["capture_manifest_path"])),
        )
        for label, variant, graph_path, capture_path in variants:
            rows.append(
                {
                    "record_id": f"{pair_id}_{variant}",
                    "pair_id": pair_id,
                    "split": split_by_pair[pair_id],
                    "variant": variant,
                    "label": label,
                    "effect_family": "slash",
                    "target_axis": "contact_focus",
                    "features": _features(_read_json(graph_path), capture_path),
                    "evidence": {
                        "graph_path": graph_path.as_posix(),
                        "capture_manifest_path": capture_path.as_posix(),
                        "teacher_rule_id": manifest["teacher_rule"]["record_id"],
                    },
                    "label_scope": "relative_slash_contact_focus_within_verified_pair",
                }
            )
    split_counts = {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")}
    overlap = sum(
        bool({row["pair_id"] for row in rows if row["split"] == a} & {row["pair_id"] for row in rows if row["split"] == b})
        for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))
    )
    metadata = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_ablation_manifest": manifest_path.resolve().as_posix(),
        "source_ablation_report": report_path.resolve().as_posix(),
        "teacher_rule_id": manifest["teacher_rule"]["record_id"],
        "target_scope": {"effect_family": "slash", "judgment_axis": "contact_focus"},
        "pair_count": len(split_by_pair),
        "record_count": len(rows),
        "split_counts": split_counts,
        "pair_split_overlap_count": overlap,
        "feature_names": list(FEATURE_NAMES),
        "files": {"records": "records.jsonl"},
        "status": "pass" if len(rows) == len(split_by_pair) * 2 and overlap == 0 and all(split_counts.values()) else "blocked",
        "limitations": [
            "Labels supervise slash contact-hit placement only.",
            "The model does not judge blade silhouette, directional trail, residual rhythm or global slash quality.",
        ],
    }
    return {"manifest": _write_json(output_root / "dataset_manifest.json", metadata), "records": _write_jsonl(output_root / "records.jsonl", rows)}


def _pairs(rows: list[dict[str, Any]], split: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        if row["split"] == split:
            grouped.setdefault(row["pair_id"], {})[int(row["label"])] = row
    return [(variants[0], variants[1]) for variants in grouped.values() if set(variants) == {0, 1}]


def _normalized(rows: list[dict[str, Any]], mean: Tensor, scale: Tensor) -> Tensor:
    return (torch.tensor([feature_vector(row) for row in rows], dtype=torch.float32) - mean) / scale


def _evaluate(model: CoreRuleRanker, pairs: list[tuple[dict[str, Any], dict[str, Any]]], mean: Tensor, scale: Tensor) -> dict[str, float]:
    model.eval()
    with torch.inference_mode():
        margins = model(_normalized([pair[1] for pair in pairs], mean, scale)) - model(_normalized([pair[0] for pair in pairs], mean, scale))
    return {
        "pair_count": float(len(pairs)),
        "pair_accuracy": float((margins > 0).float().mean().item()),
        "mean_margin": float(margins.mean().item()),
        "min_margin": float(margins.min().item()),
    }


def train_model(dataset_root: Path, output_dir: Path, epochs: int = 300, learning_rate: float = 0.01, hidden_dim: int = 10, seed: int = 20260913) -> dict[str, Path]:
    dataset_root, output_dir = dataset_root.resolve(), output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"slash hit model output already exists and is not empty: {output_dir}")
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    expected_scope = {"effect_family": "slash", "judgment_axis": "contact_focus"}
    if manifest.get("status") != "pass" or manifest.get("target_scope") != expected_scope:
        raise ValueError("passing slash/contact_focus dataset is required")
    rows = _read_jsonl(dataset_root / manifest["files"]["records"])
    pairs_by_split = {split: _pairs(rows, split) for split in ("train", "validation", "test")}
    train_rows = [row for pair in pairs_by_split["train"] for row in pair]
    matrix = torch.tensor([feature_vector(row) for row in train_rows], dtype=torch.float32)
    mean, scale = matrix.mean(dim=0), matrix.std(dim=0, unbiased=False).clamp_min(1e-6)
    normalized_train = (matrix - mean) / scale
    thresholds = {
        "l2_distance_max": float(torch.linalg.vector_norm(normalized_train, dim=1).max().item() * 1.5 + 1e-6),
        "max_abs_z": float(normalized_train.abs().amax(dim=1).max().item() * 1.5 + 1e-6),
    }
    torch.manual_seed(seed)
    random.seed(seed)
    model = CoreRuleRanker(len(FEATURE_NAMES), hidden_dim)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    best_state: dict[str, Tensor] | None = None
    best_margin = float("-inf")
    for epoch in range(1, epochs + 1):
        ordered = list(pairs_by_split["train"])
        random.Random(seed + epoch).shuffle(ordered)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        margins = model(_normalized([pair[1] for pair in ordered], mean, scale)) - model(_normalized([pair[0] for pair in ordered], mean, scale))
        loss = torch.nn.functional.softplus(-margins).mean()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        validation = _evaluate(model, pairs_by_split["validation"], mean, scale)
        if validation["mean_margin"] > best_margin:
            best_margin = validation["mean_margin"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError("slash hit ranker did not produce a checkpoint")
    model.load_state_dict(best_state)
    metrics = {split: _evaluate(model, pairs, mean, scale) for split, pairs in pairs_by_split.items()}
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "professional_slash_hit_rule_ranker.pt"
    torch.save(
        {
            "schema_version": MODEL_SCHEMA,
            "model_version": MODEL_VERSION,
            "state_dict": {key: value.cpu() for key, value in model.state_dict().items()},
            "normalization": {"mean": mean.tolist(), "scale": scale.tolist()},
            "ood_thresholds": thresholds,
            "config": {"input_dim": len(FEATURE_NAMES), "hidden_dim": hidden_dim},
            "feature_names": list(FEATURE_NAMES),
            "target_scope": manifest["target_scope"],
            "teacher_rule_id": manifest["teacher_rule_id"],
        },
        checkpoint,
    )
    metrics_path = _write_json(
        output_dir / "metrics.json",
        {
            "schema_version": MODEL_SCHEMA,
            "model_version": MODEL_VERSION,
            "dataset_id": manifest["dataset_id"],
            "metrics": metrics,
            "ood_thresholds": thresholds,
            "gradient_descent": {
                "optimizer": "AdamW",
                "epochs": epochs,
                "learning_rate": learning_rate,
                "pairwise_loss": "softplus(-(contact_aligned_score-center_misplaced_score))",
            },
            "professional_teacher_rule_count": 1,
            "human_aesthetic_labels_used": 0,
            "status": "pilot_narrow_axis_not_general_quality",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    card = output_dir / "MODEL_CARD.md"
    card.write_text(
        f"# Professional Slash Hit Rule Ranker\n\nStatus: `pilot_narrow_axis_not_general_quality`.\n\n"
        f"This PyTorch MLP uses `{manifest['pair_count']}` verified center/aligned contact-hit pairs. "
        "It predicts only `slash/contact_focus`, not complete slash quality.\n\n"
        f"Test pair accuracy: `{metrics['test']['pair_accuracy']:.4f}` across `{int(metrics['test']['pair_count'])}` held-out pairs.\n",
        encoding="utf-8",
    )
    return {"checkpoint": checkpoint, "metrics": metrics_path, "model_card": card}


def prepare_evaluation_capture(generation_manifest_path: Path, output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"slash hit evaluation output already exists and is not empty: {output_root}")
    source = _read_json(generation_manifest_path.resolve())
    evaluation = json.loads(json.dumps(source, ensure_ascii=False))
    evaluation["run_id"] = f"{source['run_id']}_hit_eval"
    evaluation["capture_protocol"] = CAPTURE_PROTOCOL
    requests = []
    for candidate in evaluation["candidates"]:
        compile_result = _read_json(_resolve(candidate["compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required for slash hit evaluation: {candidate['candidate_id']}")
        root = output_root / "runtime_captures" / candidate["candidate_id"]
        candidate["capture_manifest_path"] = (root / "capture_manifest.json").as_posix()
        requests.append(
            {
                "candidate_id": candidate["candidate_id"],
                "prefab_path": compile_result["output_prefab_path"],
                "capture_dir": (root / "captures").as_posix(),
                "capture_manifest_path": (root / "capture_manifest.json").as_posix(),
                "material_timeline_path": (root / "material_timeline.json").as_posix(),
                "source_script_fidelity": "generated_graph_no_source_scripts",
                "ignored_script_dependency_count": 0,
                "missing_script_count": 0,
                "capture_category": "slash",
                "forced_camera_view": "front",
                "force_orthographic": True,
                "forced_orthographic_size": ORTHOGRAPHIC_SIZE,
            }
        )
    return {
        "manifest": _write_json(output_root / "evaluation_manifest.json", evaluation),
        "runtime_request": _write_json(
            output_root / "render_requests.json",
            {
                "schema_version": "effectdemo_source_render_requests.v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "run_id": evaluation["run_id"],
                "scene": "SlashHitRuleEvaluation",
                "camera": "SlashHitRuleEvaluationCamera",
                "width": 640,
                "height": 640,
                "sampling_mode": "adaptive_runtime",
                "sampling": {
                    "target_intervals": 24,
                    "short_effect_target_intervals": 24,
                    "min_interval_seconds": 0.01,
                    "max_interval_seconds": 0.025,
                    "max_duration_seconds": 0.6,
                    "include_zero": True,
                    "duration_sources": ["particle_system"],
                },
                "capture_material_timeline": True,
                "requests": requests,
            },
        ),
    }


def rank_batch(checkpoint_path: Path, generation_manifest_path: Path, output_path: Path) -> Path:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    expected_scope = {"effect_family": "slash", "judgment_axis": "contact_focus"}
    if payload.get("schema_version") != MODEL_SCHEMA or payload.get("target_scope") != expected_scope or tuple(payload.get("feature_names") or ()) != FEATURE_NAMES:
        raise ValueError("checkpoint is not a compatible slash/contact_focus model")
    manifest = _read_json(generation_manifest_path.resolve())
    if manifest.get("capture_protocol") != CAPTURE_PROTOCOL:
        raise ValueError(f"slash hit ranking requires capture protocol {CAPTURE_PROTOCOL}")
    model = CoreRuleRanker(int(payload["config"]["input_dim"]), int(payload["config"]["hidden_dim"]))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    mean = torch.tensor(payload["normalization"]["mean"], dtype=torch.float32)
    scale = torch.tensor(payload["normalization"]["scale"], dtype=torch.float32)
    limits = payload["ood_thresholds"]
    rows = []
    for candidate in manifest["candidates"]:
        graph = _read_json(_resolve(candidate["graph_path"]))
        features = _features(graph, _resolve(candidate["capture_manifest_path"]))
        vector = (torch.tensor([features[name] for name in FEATURE_NAMES], dtype=torch.float32) - mean) / scale
        l2 = float(torch.linalg.vector_norm(vector).item())
        max_abs = float(vector.abs().max().item())
        with torch.inference_mode():
            score = float(model(vector.unsqueeze(0))[0].item())
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "graph_id": candidate["graph_id"],
                "contact_focus_score": score,
                "distribution": {
                    "in_distribution": l2 <= float(limits["l2_distance_max"]),
                    "l2_distance": l2,
                    "l2_limit": float(limits["l2_distance_max"]),
                    "max_abs_z": max_abs,
                    "max_abs_z_diagnostic_limit": float(limits["max_abs_z"]),
                    "gate": "l2_distance",
                },
                "capture_manifest_path": _resolve(candidate["capture_manifest_path"]).as_posix(),
            }
        )
    rows.sort(key=lambda row: (not row["distribution"]["in_distribution"], -row["contact_focus_score"], row["candidate_id"]))
    in_distribution_count = sum(row["distribution"]["in_distribution"] for row in rows)
    return _write_json(
        output_path.resolve(),
        {
            "schema_version": "vfx_professional_slash_hit_rule_ranking.v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_path": checkpoint_path.resolve().as_posix(),
            "model_version": payload["model_version"],
            "target_scope": payload["target_scope"],
            "capture_protocol": CAPTURE_PROTOCOL,
            "candidate_count": len(rows),
            "in_distribution_count": in_distribution_count,
            "ranking": rows,
            "score_interpretation": "Uncalibrated relative proposal score for slash/contact_focus only; not global slash quality.",
            "status": "pass" if rows and in_distribution_count else "blocked_out_of_distribution" if rows else "blocked_no_candidates",
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, train and apply the slash contact-hit model.")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("prepare-evaluation")
    evaluate.add_argument("--generation-manifest", type=Path, required=True)
    evaluate.add_argument("--output-root", type=Path, required=True)
    build = commands.add_parser("build-dataset")
    build.add_argument("--ablation-manifest", type=Path, required=True)
    build.add_argument("--ablation-report", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--dataset-id", default="professional_slash_hit_rule_training_r001")
    train = commands.add_parser("train")
    train.add_argument("--dataset-root", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--epochs", type=int, default=300)
    train.add_argument("--learning-rate", type=float, default=0.01)
    train.add_argument("--hidden-dim", type=int, default=10)
    train.add_argument("--seed", type=int, default=20260913)
    rank = commands.add_parser("rank")
    rank.add_argument("--checkpoint", type=Path, required=True)
    rank.add_argument("--generation-manifest", type=Path, required=True)
    rank.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-evaluation":
            paths = prepare_evaluation_capture(args.generation_manifest, args.output_root)
        elif args.command == "build-dataset":
            paths = build_dataset(args.ablation_manifest, args.ablation_report, args.output_root, args.dataset_id)
        elif args.command == "train":
            paths = train_model(args.dataset_root, args.output_dir, args.epochs, args.learning_rate, args.hidden_dim, args.seed)
        else:
            paths = {"ranking": rank_batch(args.checkpoint, args.generation_manifest, args.output)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
