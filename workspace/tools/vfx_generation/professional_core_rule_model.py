"""Build and train the narrow explosion core-readability Teacher model."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn

from .professional_explosion_material_teacher_reproduction import _variant_summary
from .professional_teacher_guided_generation import _single_role_component


DATASET_SCHEMA = "vfx_professional_core_rule_training.v2"
MODEL_SCHEMA = "vfx_professional_core_rule_ranker.v2"
MODEL_VERSION = "professional_core_rule_ranker_mlp.v2"
CAPTURE_PROTOCOL = "core_readability_fixed_orthographic_v1"
IMAGE_FEATURE_NAMES = (
    "image.visible_ratio.mean",
    "image.visible_ratio.max",
    "image.visible_ratio.std",
    "image.mean_luma.mean",
    "image.mean_luma.max",
    "image.std_luma.mean",
    "image.std_luma.max",
    "image.overexposed_ratio.mean",
    "image.overexposed_ratio.max",
    "image.edge_density.mean",
    "image.edge_density.max",
    "image.temporal_delta.mean",
    "image.temporal_delta.max",
    "image.bbox_area_ratio.mean",
    "image.bbox_area_ratio.max",
)
CENTER_FEATURE_NAMES = (
    "center_luminance.mean",
    "center_luminance.max",
    "center_luminance.std",
    "center_local_contrast.mean",
    "center_local_contrast.max",
    "center_local_contrast.std",
    "center_occupancy.mean",
    "center_occupancy.max",
)
CORE_LOCAL_FEATURE_NAMES = (
    "core.visible_area_ratio",
    "core.bbox_fill_ratio",
    "core.visible_luma_mean",
    "core.visible_luma_std",
    "core.edge_density",
    "core.center_luminance",
)
FEATURE_NAMES = CORE_LOCAL_FEATURE_NAMES


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


def _core_window_end(graph: dict[str, Any]) -> float:
    support = _single_role_component(graph, "particle_systems", "support")
    return max(0.025, float(support["parameters"].get("start_delay_max") or 0.05) - 0.005)


def _capture_features(manifest_path: Path, max_time_seconds: float) -> dict[str, float]:
    peak = _variant_summary(manifest_path.resolve(), max_time_seconds)["peak"]
    return {name: float(peak[name.removeprefix("core.")]) for name in FEATURE_NAMES}


def _pair_splits(pair_ids: list[str]) -> dict[str, str]:
    ordered = sorted(set(pair_ids), key=lambda value: hashlib.sha256(f"professional_core_split.v1|{value}".encode("utf-8")).hexdigest())
    if len(ordered) < 6:
        raise ValueError("at least six verified Teacher-transfer pairs are required")
    validation_count = max(1, len(ordered) // 4)
    test_count = max(1, len(ordered) // 4)
    train_count = len(ordered) - validation_count - test_count
    if train_count < 2:
        raise ValueError("at least two training pairs are required")
    result = {}
    for index, pair_id in enumerate(ordered):
        result[pair_id] = "train" if index < train_count else "validation" if index < train_count + validation_count else "test"
    return result


def build_dataset(guided_manifest_path: Path, guided_report_path: Path, output_root: Path, dataset_id: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional core dataset output already exists and is not empty: {output_root}")
    guided_manifest = _read_json(guided_manifest_path.resolve())
    guided_report = _read_json(guided_report_path.resolve())
    if guided_report.get("status") != "pass":
        raise ValueError("passing professional Teacher-guided report is required")
    report_by_id = {row["candidate_id"]: row for row in guided_report["records"]}
    pair_ids = [row["candidate_id"] for row in guided_manifest["candidates"] if report_by_id[row["candidate_id"]]["professional_rule_transfer_pass"]]
    split_by_pair = _pair_splits(pair_ids)
    rows: list[dict[str, Any]] = []
    for candidate in guided_manifest["candidates"]:
        pair_id = candidate["candidate_id"]
        report = report_by_id[pair_id]
        if pair_id not in split_by_pair or not report["technical_pass"]:
            continue
        baseline_path = guided_manifest_path.resolve().parent / "runtime_baselines" / pair_id / "capture_manifest.json"
        guided_path = _resolve(candidate["capture_manifest_path"])
        graph = _read_json(_resolve(candidate["guided_graph_path"]))
        core_window_end = _core_window_end(graph)
        for label, variant, capture_path in ((0, "baseline", baseline_path), (1, "teacher_guided", guided_path)):
            rows.append({
                "record_id": f"{pair_id}_{variant}",
                "pair_id": pair_id,
                "split": split_by_pair[pair_id],
                "variant": variant,
                "label": label,
                "target_axis": "core_readability",
                "effect_family": "explosion",
                "core_only_window_end_seconds": core_window_end,
                "image_features": _capture_features(capture_path, core_window_end),
                "evidence": {
                    "capture_manifest_path": capture_path.resolve().as_posix(),
                    "teacher_rule_id": guided_manifest["teacher_rule"]["record_id"],
                    "teacher_guided_report_path": guided_report_path.resolve().as_posix(),
                    "professional_rule_transfer_pass": True,
                },
                "label_scope": "relative_core_readability_within_verified_pair",
            })
    split_counts = {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")}
    pair_split_overlap = sum(
        bool({row["pair_id"] for row in rows if row["split"] == left} & {row["pair_id"] for row in rows if row["split"] == right})
        for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))
    )
    manifest = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_guided_manifest": guided_manifest_path.resolve().as_posix(),
        "source_guided_report": guided_report_path.resolve().as_posix(),
        "teacher_rule_id": guided_manifest["teacher_rule"]["record_id"],
        "target_scope": {"effect_family": "explosion", "judgment_axis": "core_readability"},
        "pair_count": len(split_by_pair),
        "record_count": len(rows),
        "split_counts": split_counts,
        "pair_split_overlap_count": pair_split_overlap,
        "feature_names": list(FEATURE_NAMES),
        "label_counts": {"weaker_baseline": sum(row["label"] == 0 for row in rows), "teacher_guided": sum(row["label"] == 1 for row in rows)},
        "supervision": {
            "professional_teacher_rule_count": 1,
            "verified_unity_transfer_pair_count": len(split_by_pair),
            "nonexpert_aesthetic_labels_used": 0,
            "global_quality_labels_used": 0,
        },
        "files": {"records": "records.jsonl"},
        "status": "pass" if len(rows) == len(split_by_pair) * 2 and pair_split_overlap == 0 and all(split_counts.values()) else "blocked",
        "limitations": [
            "Labels express relative core readability inside verified explosion pairs only.",
            "The dataset does not supervise overall quality, style, rhythm, material quality or other effect families.",
            "The dataset is a small pilot and cannot establish broad generalization.",
        ],
    }
    records_path = _write_jsonl(output_root / "records.jsonl", rows)
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {"manifest": manifest_path, "records": records_path}


def feature_vector(row: dict[str, Any]) -> list[float]:
    features = row.get("image_features") or {}
    return [float(features.get(name) or 0.0) for name in FEATURE_NAMES]


def prepare_evaluation_capture(generation_manifest_path: Path, output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"core readability evaluation output already exists and is not empty: {output_root}")
    source = _read_json(generation_manifest_path.resolve())
    if source.get("effect_family") != "explosion":
        raise ValueError("core readability evaluation requires an explosion generation manifest")
    evaluation = json.loads(json.dumps(source, ensure_ascii=False))
    evaluation["run_id"] = f"{source['run_id']}_core_readability_eval"
    evaluation["capture_protocol"] = CAPTURE_PROTOCOL
    requests = []
    for candidate in evaluation["candidates"]:
        compile_result = _read_json(_resolve(candidate["compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required for core readability evaluation: {candidate['candidate_id']}")
        root = output_root / "runtime_captures" / candidate["candidate_id"]
        candidate["capture_manifest_path"] = (root / "capture_manifest.json").as_posix()
        requests.append({"candidate_id": candidate["candidate_id"], "prefab_path": compile_result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 1.5})
    return {"manifest": _write_json(output_root / "evaluation_manifest.json", evaluation), "runtime_request": _write_json(output_root / "render_requests.json", {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": evaluation["run_id"], "scene": "CoreReadabilityRuleEvaluation", "camera": "CoreReadabilityRuleEvaluationCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 0.8, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})}


class CoreRuleRanker(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 12) -> None:
        super().__init__()
        self.network = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 1))

    def forward(self, inputs: Tensor) -> Tensor:
        return self.network(inputs).squeeze(-1)


def _pairs(rows: list[dict[str, Any]], split: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        if row["split"] == split:
            grouped.setdefault(row["pair_id"], {})[int(row["label"])] = row
    pairs = []
    for pair_id, variants in grouped.items():
        if set(variants) != {0, 1}:
            raise ValueError(f"pair {pair_id} does not contain baseline and Teacher-guided variants")
        pairs.append((variants[0], variants[1]))
    return pairs


def _normalized_tensor(rows: list[dict[str, Any]], mean: Tensor, scale: Tensor) -> Tensor:
    return (torch.tensor([feature_vector(row) for row in rows], dtype=torch.float32) - mean) / scale


def _evaluate(model: CoreRuleRanker, pairs: list[tuple[dict[str, Any], dict[str, Any]]], mean: Tensor, scale: Tensor) -> dict[str, float]:
    model.eval()
    with torch.inference_mode():
        negative = _normalized_tensor([pair[0] for pair in pairs], mean, scale)
        positive = _normalized_tensor([pair[1] for pair in pairs], mean, scale)
        margins = model(positive) - model(negative)
    return {
        "pair_count": float(len(pairs)),
        "pair_accuracy": float((margins > 0).float().mean().item()),
        "mean_margin": float(margins.mean().item()),
        "min_margin": float(margins.min().item()),
    }


def train_model(dataset_root: Path, output_dir: Path, epochs: int = 300, learning_rate: float = 0.01, hidden_dim: int = 12, seed: int = 20260903) -> dict[str, Path]:
    dataset_root = dataset_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"professional core model output already exists and is not empty: {output_dir}")
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    if manifest.get("status") != "pass" or manifest.get("target_scope") != {"effect_family": "explosion", "judgment_axis": "core_readability"}:
        raise ValueError("passing explosion/core_readability Teacher dataset is required")
    rows = _read_jsonl(dataset_root / manifest["files"]["records"])
    pairs_by_split = {split: _pairs(rows, split) for split in ("train", "validation", "test")}
    if not all(pairs_by_split.values()):
        raise ValueError("all pair splits must be non-empty")
    train_rows = [row for pair in pairs_by_split["train"] for row in pair]
    train_matrix = torch.tensor([feature_vector(row) for row in train_rows], dtype=torch.float32)
    mean = train_matrix.mean(dim=0)
    scale = train_matrix.std(dim=0, unbiased=False).clamp_min(1e-6)
    normalized_train = (train_matrix - mean) / scale
    train_l2 = torch.linalg.vector_norm(normalized_train, dim=1)
    train_max_abs = normalized_train.abs().amax(dim=1)
    ood_thresholds = {
        "l2_distance_max": float(train_l2.max().item() * 1.5 + 1e-6),
        "max_abs_z": float(train_max_abs.max().item() * 1.5 + 1e-6),
    }
    torch.manual_seed(seed)
    random.seed(seed)
    model = CoreRuleRanker(len(FEATURE_NAMES), hidden_dim)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    best_state: dict[str, Tensor] | None = None
    best_validation_margin = float("-inf")
    history = []
    for epoch in range(1, epochs + 1):
        ordered = list(pairs_by_split["train"])
        random.Random(seed + epoch).shuffle(ordered)
        negative = _normalized_tensor([pair[0] for pair in ordered], mean, scale)
        positive = _normalized_tensor([pair[1] for pair in ordered], mean, scale)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        margins = model(positive) - model(negative)
        loss = torch.nn.functional.softplus(-margins).mean()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        validation = _evaluate(model, pairs_by_split["validation"], mean, scale)
        history.append({"epoch": epoch, "loss": float(loss.item()), **validation})
        if validation["mean_margin"] > best_validation_margin:
            best_validation_margin = validation["mean_margin"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError("professional core ranker did not produce a checkpoint")
    model.load_state_dict(best_state)
    metrics = {split: _evaluate(model, pairs, mean, scale) for split, pairs in pairs_by_split.items()}

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "professional_core_rule_ranker.pt"
    torch.save({
        "schema_version": MODEL_SCHEMA,
        "model_version": MODEL_VERSION,
        "state_dict": {key: value.cpu() for key, value in model.state_dict().items()},
        "normalization": {"mean": mean.tolist(), "scale": scale.tolist()},
        "ood_thresholds": ood_thresholds,
        "config": {"input_dim": len(FEATURE_NAMES), "hidden_dim": hidden_dim},
        "feature_names": list(FEATURE_NAMES),
        "target_scope": manifest["target_scope"],
        "teacher_rule_id": manifest["teacher_rule_id"],
    }, checkpoint)
    predictions = []
    model.eval()
    with torch.inference_mode():
        values = model(_normalized_tensor(rows, mean, scale)).tolist()
    for row, value in zip(rows, values):
        predictions.append({"record_id": row["record_id"], "pair_id": row["pair_id"], "split": row["split"], "variant": row["variant"], "label": row["label"], "core_readability_score": float(value)})
    metrics_path = _write_json(output_dir / "metrics.json", {
        "schema_version": MODEL_SCHEMA,
        "model_version": MODEL_VERSION,
        "dataset_id": manifest["dataset_id"],
        "metrics": metrics,
        "gradient_descent": {"optimizer": "AdamW", "epochs": epochs, "learning_rate": learning_rate, "pairwise_loss": "softplus(-(guided_score-baseline_score))"},
        "ood_thresholds": ood_thresholds,
        "professional_teacher_rule_count": 1,
        "human_aesthetic_labels_used": 0,
        "status": "pilot_narrow_axis_not_general_quality",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    predictions_path = _write_jsonl(output_dir / "predictions.jsonl", predictions)
    card_path = output_dir / "MODEL_CARD.md"
    card_path.write_text(
        f"# Professional Core Rule Ranker\n\n"
        f"Status: `pilot_narrow_axis_not_general_quality`.\n\n"
        f"This PyTorch MLP uses pairwise gradient descent over `{manifest['pair_count']}` verified Unity baseline/Teacher-guided explosion pairs. "
        f"It predicts only relative `explosion/core_readability`; it is not a general VFX quality model and must not score other effect families or aesthetic axes.\n\n"
        f"Test pair accuracy: `{metrics['test']['pair_accuracy']:.4f}` across `{int(metrics['test']['pair_count'])}` held-out pairs. "
        "The test set is intentionally tiny, so this checkpoint is a pipeline proof and proposal-ranking prior, not production evidence.\n",
        encoding="utf-8",
    )
    return {"checkpoint": checkpoint, "metrics": metrics_path, "predictions": predictions_path, "model_card": card_path}


def rank_guided_batch(checkpoint_path: Path, guided_manifest_path: Path, output_path: Path) -> Path:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    if payload.get("schema_version") != MODEL_SCHEMA:
        raise ValueError("unsupported professional core ranker checkpoint")
    if payload.get("target_scope") != {"effect_family": "explosion", "judgment_axis": "core_readability"}:
        raise ValueError("checkpoint is not scoped to explosion/core_readability")
    if tuple(payload.get("feature_names") or ()) != FEATURE_NAMES:
        raise ValueError("checkpoint feature order does not match the current extractor")
    model = CoreRuleRanker(int(payload["config"]["input_dim"]), int(payload["config"]["hidden_dim"]))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    mean = torch.tensor(payload["normalization"]["mean"], dtype=torch.float32)
    scale = torch.tensor(payload["normalization"]["scale"], dtype=torch.float32)
    thresholds = payload.get("ood_thresholds") or {}
    l2_limit = float(thresholds.get("l2_distance_max") or float("inf"))
    max_abs_limit = float(thresholds.get("max_abs_z") or float("inf"))
    manifest = _read_json(guided_manifest_path.resolve())
    if manifest.get("capture_protocol") != CAPTURE_PROTOCOL:
        raise ValueError(f"core readability ranking requires capture protocol {CAPTURE_PROTOCOL}")
    rows = []
    for candidate in manifest["candidates"]:
        capture_path = _resolve(candidate["capture_manifest_path"])
        graph = _read_json(_resolve(candidate["guided_graph_path"] if candidate.get("guided_graph_path") else candidate["graph_path"]))
        features = _capture_features(capture_path, _core_window_end(graph))
        vector = (torch.tensor([float(features[name]) for name in FEATURE_NAMES], dtype=torch.float32) - mean) / scale
        l2_distance = float(torch.linalg.vector_norm(vector).item())
        max_abs_z = float(vector.abs().max().item())
        in_distribution = l2_distance <= l2_limit
        with torch.inference_mode():
            score = float(model(vector.unsqueeze(0))[0].item())
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "source_candidate_id": candidate.get("source_candidate_id"),
            "guided_graph_id": candidate.get("guided_graph_id") or candidate.get("graph_id"),
            "capture_manifest_path": capture_path.as_posix(),
            "core_readability_score": score,
            "distribution": {"in_distribution": in_distribution, "l2_distance": l2_distance, "l2_limit": l2_limit, "max_abs_z": max_abs_z, "max_abs_z_diagnostic_limit": max_abs_limit, "gate": "l2_distance"},
        })
    rows.sort(key=lambda row: (not row["distribution"]["in_distribution"], -row["core_readability_score"], row["candidate_id"]))
    return _write_json(output_path.resolve(), {
        "schema_version": "vfx_professional_core_rule_ranking.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_path": checkpoint_path.resolve().as_posix(),
        "model_version": payload["model_version"],
        "target_scope": payload["target_scope"],
        "candidate_count": len(rows),
        "ranking": rows,
        "score_interpretation": "Uncalibrated relative proposal score for explosion/core_readability only; not an overall aesthetic score.",
        "in_distribution_count": sum(row["distribution"]["in_distribution"] for row in rows),
        "status": "pass" if rows and any(row["distribution"]["in_distribution"] for row in rows) else "blocked_out_of_distribution" if rows else "blocked_no_candidates",
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and train a narrow professional explosion core-readability model.")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("prepare-evaluation")
    evaluate.add_argument("--generation-manifest", type=Path, required=True)
    evaluate.add_argument("--output-root", type=Path, required=True)
    build = commands.add_parser("build-dataset")
    build.add_argument("--guided-manifest", type=Path, required=True)
    build.add_argument("--guided-report", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--dataset-id", default="professional_core_rule_training_r001")
    train = commands.add_parser("train")
    train.add_argument("--dataset-root", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--epochs", type=int, default=300)
    train.add_argument("--learning-rate", type=float, default=0.01)
    train.add_argument("--hidden-dim", type=int, default=12)
    train.add_argument("--seed", type=int, default=20260903)
    rank = commands.add_parser("rank")
    rank.add_argument("--checkpoint", type=Path, required=True)
    rank.add_argument("--guided-manifest", type=Path, required=True)
    rank.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-evaluation":
            paths = prepare_evaluation_capture(args.generation_manifest, args.output_root)
        elif args.command == "build-dataset":
            paths = build_dataset(args.guided_manifest, args.guided_report, args.output_root, args.dataset_id)
        elif args.command == "train":
            paths = train_model(args.dataset_root, args.output_dir, args.epochs, args.learning_rate, args.hidden_dim, args.seed)
        else:
            paths = {"ranking": rank_guided_batch(args.checkpoint, args.guided_manifest, args.output)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
