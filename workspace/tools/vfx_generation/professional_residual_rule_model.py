"""Train and apply the narrow explosion residual-persistence Teacher model."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

from .professional_core_rule_model import CoreRuleRanker, _pair_splits
from .professional_residual_teacher_reproduction import _late_metrics, _non_residual_end_seconds
from .professional_teacher_reproduction import _capture_summary


DATASET_SCHEMA = "vfx_professional_residual_rule_training.v2"
MODEL_SCHEMA = "vfx_professional_residual_rule_ranker.v2"
MODEL_VERSION = "professional_residual_rule_ranker_mlp.v2"
CAPTURE_PROTOCOL = "residual_fixed_orthographic_v1"
RESIDUAL_FEATURE_NAMES = (
    "late.active_frame_ratio",
    "late.visible_area_mean",
    "late.visible_area_max",
    "late.last_visible_time_seconds",
    "late.center_luminance.mean",
    "late.center_luminance.max",
    "late.center_local_contrast.mean",
    "late.center_local_contrast.max",
)
FEATURE_NAMES = RESIDUAL_FEATURE_NAMES


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


def _capture_features(manifest_path: Path, late_start: float) -> dict[str, float]:
    manifest_path = manifest_path.resolve()
    manifest = _read_json(manifest_path)
    if not manifest.get("image_sequence_training_eligible") or int(manifest.get("material_render_error_frame_count") or 0) > 0:
        raise ValueError(f"capture is not eligible for residual training: {manifest_path}")
    capture_root = _resolve(str(manifest.get("capture_root") or manifest_path.parent / "captures"))
    frames = [row for row in manifest.get("frames") or [] if row.get("valid") and row.get("path")]
    frame_paths = [capture_root / str(row["path"]) for row in frames]
    if not frames or any(not path.is_file() for path in frame_paths):
        raise FileNotFoundError(f"eligible residual frame is missing: {manifest_path}")
    summary = _capture_summary(manifest_path)
    late = _late_metrics(summary, late_start)
    late_frames = [row for row in summary["frames"] if float(row["time_seconds"]) >= late_start]

    def values(name: str) -> np.ndarray:
        return np.asarray([float(row[name]) for row in late_frames], dtype=np.float64)

    luma = values("center_luminance")
    contrast = values("center_local_contrast")
    visible = values("visible_area_ratio")
    features = {
        "late.active_frame_ratio": late["active_frame_ratio"],
        "late.visible_area_mean": late["visible_area_mean"],
        "late.visible_area_max": float(visible.max()) if visible.size else 0.0,
        "late.last_visible_time_seconds": late["last_visible_time_seconds"],
        "late.center_luminance.mean": float(luma.mean()) if luma.size else 0.0,
        "late.center_luminance.max": float(luma.max()) if luma.size else 0.0,
        "late.center_local_contrast.mean": float(contrast.mean()) if contrast.size else 0.0,
        "late.center_local_contrast.max": float(contrast.max()) if contrast.size else 0.0,
    }
    return features


def feature_vector(row: dict[str, Any]) -> list[float]:
    features = row.get("image_features") or {}
    return [float(features.get(name) or 0.0) for name in FEATURE_NAMES]


def prepare_evaluation_capture(generation_manifest_path: Path, output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"residual evaluation output already exists and is not empty: {output_root}")
    source = _read_json(generation_manifest_path.resolve())
    if source.get("effect_family") != "explosion":
        raise ValueError("residual evaluation requires an explosion generation manifest")
    evaluation = json.loads(json.dumps(source, ensure_ascii=False))
    evaluation["run_id"] = f"{source['run_id']}_residual_eval"
    evaluation["capture_protocol"] = CAPTURE_PROTOCOL
    evaluation["source_generation_manifest"] = generation_manifest_path.resolve().as_posix()
    requests = []
    for candidate in evaluation["candidates"]:
        compile_result = _read_json(_resolve(candidate["compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required for residual evaluation: {candidate['candidate_id']}")
        case_root = output_root / "runtime_captures" / candidate["candidate_id"]
        candidate["capture_manifest_path"] = (case_root / "capture_manifest.json").as_posix()
        requests.append({
            "candidate_id": candidate["candidate_id"],
            "prefab_path": compile_result["output_prefab_path"],
            "capture_dir": (case_root / "captures").as_posix(),
            "capture_manifest_path": (case_root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (case_root / "material_timeline.json").as_posix(),
            "source_script_fidelity": "generated_graph_no_source_scripts",
            "ignored_script_dependency_count": 0,
            "missing_script_count": 0,
            "capture_category": "explosion",
            "forced_camera_view": "front",
        })
    manifest_path = _write_json(output_root / "evaluation_manifest.json", evaluation)
    request_path = _write_json(output_root / "render_requests.json", {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": evaluation["run_id"],
        "scene": "ResidualRuleEvaluation",
        "camera": "ResidualRuleEvaluationCamera",
        "width": 512,
        "height": 512,
        "sampling_mode": "adaptive_runtime",
        "sampling": {"target_intervals": 32, "short_effect_target_intervals": 32, "min_interval_seconds": 0.01, "max_interval_seconds": 0.05, "max_duration_seconds": 2.5, "include_zero": True, "duration_sources": ["particle_system"]},
        "capture_material_timeline": True,
        "requests": requests,
    })
    return {"manifest": manifest_path, "runtime_request": request_path}


def build_dataset(ablation_manifest_path: Path, ablation_report_path: Path, output_root: Path, dataset_id: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional residual dataset output already exists and is not empty: {output_root}")
    manifest = _read_json(ablation_manifest_path.resolve())
    report = _read_json(ablation_report_path.resolve())
    if report.get("status") != "pass":
        raise ValueError("passing professional residual ablation report is required")
    report_by_id = {row["candidate_id"]: row for row in report["records"]}
    pair_ids = [row["candidate_id"] for row in manifest["candidates"] if report_by_id[row["candidate_id"]]["professional_rule_transfer_pass"]]
    split_by_pair = _pair_splits(pair_ids)
    rows = []
    for candidate in manifest["candidates"]:
        pair_id = candidate["candidate_id"]
        if pair_id not in split_by_pair:
            continue
        late_start = float(candidate["late_window_start_seconds"])
        for label, variant, capture_path in (
            (0, "abrupt_no_residual", _resolve(candidate["baseline_capture_manifest_path"])),
            (1, "staged_residual", _resolve(candidate["capture_manifest_path"])),
        ):
            rows.append({
                "record_id": f"{pair_id}_{variant}", "pair_id": pair_id, "split": split_by_pair[pair_id], "variant": variant, "label": label,
                "target_axis": "residual_persistence", "effect_family": "explosion", "late_window_start_seconds": late_start,
                "image_features": _capture_features(capture_path, late_start),
                "evidence": {"capture_manifest_path": capture_path.as_posix(), "teacher_rule_id": manifest["teacher_rule"]["record_id"], "teacher_ablation_report_path": ablation_report_path.resolve().as_posix(), "professional_rule_transfer_pass": True},
                "label_scope": "relative_residual_persistence_within_verified_pair",
            })
    split_counts = {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")}
    overlap = sum(bool({row["pair_id"] for row in rows if row["split"] == a} & {row["pair_id"] for row in rows if row["split"] == b}) for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")))
    dataset_manifest = {
        "schema_version": DATASET_SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(), "dataset_id": dataset_id,
        "source_ablation_manifest": ablation_manifest_path.resolve().as_posix(), "source_ablation_report": ablation_report_path.resolve().as_posix(),
        "teacher_rule_id": manifest["teacher_rule"]["record_id"], "target_scope": {"effect_family": "explosion", "judgment_axis": "residual_persistence"},
        "pair_count": len(split_by_pair), "record_count": len(rows), "split_counts": split_counts, "pair_split_overlap_count": overlap,
        "feature_names": list(FEATURE_NAMES), "label_counts": {"abrupt_no_residual": sum(row["label"] == 0 for row in rows), "staged_residual": sum(row["label"] == 1 for row in rows)},
        "supervision": {"professional_teacher_rule_count": 1, "verified_unity_transfer_pair_count": len(split_by_pair), "nonexpert_aesthetic_labels_used": 0, "global_quality_labels_used": 0},
        "files": {"records": "records.jsonl"}, "status": "pass" if len(rows) == len(split_by_pair) * 2 and overlap == 0 and all(split_counts.values()) else "blocked",
        "limitations": ["Labels express residual persistence inside verified explosion pairs only.", "The dataset does not supervise overall quality or the visual design of the residual material.", "The dataset is a small pilot and cannot establish broad generalization."],
    }
    records_path = _write_jsonl(output_root / "records.jsonl", rows)
    manifest_path = _write_json(output_root / "dataset_manifest.json", dataset_manifest)
    return {"manifest": manifest_path, "records": records_path}


def merge_datasets(dataset_roots: list[Path], output_root: Path, dataset_id: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"merged professional residual dataset output already exists and is not empty: {output_root}")
    if len(dataset_roots) < 2:
        raise ValueError("at least two residual datasets are required for merge")
    expected_scope = {"effect_family": "explosion", "judgment_axis": "residual_persistence"}
    rows_by_id: dict[str, dict[str, Any]] = {}
    sources = []
    for dataset_root in dataset_roots:
        root = dataset_root.resolve()
        manifest = _read_json(root / "dataset_manifest.json")
        if manifest.get("status") != "pass" or manifest.get("target_scope") != expected_scope:
            raise ValueError(f"passing explosion/residual_persistence dataset required: {root}")
        if tuple(manifest.get("feature_names") or ()) != FEATURE_NAMES:
            raise ValueError(f"residual feature schema mismatch: {root}")
        sources.append({"dataset_id": manifest["dataset_id"], "path": root.as_posix(), "pair_count": manifest["pair_count"]})
        for row in _read_jsonl(root / manifest["files"]["records"]):
            record_id = str(row["record_id"])
            previous = rows_by_id.get(record_id)
            if previous is not None and previous != row:
                raise ValueError(f"conflicting residual training record: {record_id}")
            rows_by_id[record_id] = row
    pair_ids = sorted({str(row["pair_id"]) for row in rows_by_id.values()})
    split_by_pair = _pair_splits(pair_ids)
    rows = []
    for record_id in sorted(rows_by_id):
        row = dict(rows_by_id[record_id])
        row["split"] = split_by_pair[str(row["pair_id"])]
        rows.append(row)
    split_counts = {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")}
    overlap = sum(bool({row["pair_id"] for row in rows if row["split"] == a} & {row["pair_id"] for row in rows if row["split"] == b}) for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")))
    merged = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_datasets": sources,
        "teacher_rule_id": manifest["teacher_rule_id"],
        "target_scope": expected_scope,
        "pair_count": len(pair_ids),
        "record_count": len(rows),
        "split_counts": split_counts,
        "pair_split_overlap_count": overlap,
        "feature_names": list(FEATURE_NAMES),
        "label_counts": {"abrupt_no_residual": sum(row["label"] == 0 for row in rows), "staged_residual": sum(row["label"] == 1 for row in rows)},
        "supervision": {"professional_teacher_rule_count": 1, "verified_unity_transfer_pair_count": len(pair_ids), "nonexpert_aesthetic_labels_used": 0, "global_quality_labels_used": 0},
        "files": {"records": "records.jsonl"},
        "status": "pass" if len(rows) == len(pair_ids) * 2 and overlap == 0 and all(split_counts.values()) else "blocked",
        "limitations": ["Labels express residual persistence inside verified explosion pairs only.", "Merged batches expand late-window coverage but do not establish broad style generalization."],
    }
    return {"manifest": _write_json(output_root / "dataset_manifest.json", merged), "records": _write_jsonl(output_root / "records.jsonl", rows)}


def _pairs(rows: list[dict[str, Any]], split: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        if row["split"] == split:
            grouped.setdefault(row["pair_id"], {})[int(row["label"])] = row
    pairs = []
    for pair_id, variants in grouped.items():
        if set(variants) != {0, 1}:
            raise ValueError(f"pair {pair_id} does not contain residual-off and residual-on variants")
        pairs.append((variants[0], variants[1]))
    return pairs


def _normalized(rows: list[dict[str, Any]], mean: Tensor, scale: Tensor) -> Tensor:
    return (torch.tensor([feature_vector(row) for row in rows], dtype=torch.float32) - mean) / scale


def _evaluate(model: CoreRuleRanker, pairs: list[tuple[dict[str, Any], dict[str, Any]]], mean: Tensor, scale: Tensor) -> dict[str, float]:
    model.eval()
    with torch.inference_mode():
        margins = model(_normalized([pair[1] for pair in pairs], mean, scale)) - model(_normalized([pair[0] for pair in pairs], mean, scale))
    return {"pair_count": float(len(pairs)), "pair_accuracy": float((margins > 0).float().mean().item()), "mean_margin": float(margins.mean().item()), "min_margin": float(margins.min().item())}


def train_model(dataset_root: Path, output_dir: Path, epochs: int = 300, learning_rate: float = 0.01, hidden_dim: int = 12, seed: int = 20260904) -> dict[str, Path]:
    dataset_root, output_dir = dataset_root.resolve(), output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"professional residual model output already exists and is not empty: {output_dir}")
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    if manifest.get("status") != "pass" or manifest.get("target_scope") != {"effect_family": "explosion", "judgment_axis": "residual_persistence"}:
        raise ValueError("passing explosion/residual_persistence Teacher dataset is required")
    rows = _read_jsonl(dataset_root / manifest["files"]["records"])
    pairs_by_split = {split: _pairs(rows, split) for split in ("train", "validation", "test")}
    if not all(pairs_by_split.values()):
        raise ValueError("all residual pair splits must be non-empty")
    train_rows = [row for pair in pairs_by_split["train"] for row in pair]
    matrix = torch.tensor([feature_vector(row) for row in train_rows], dtype=torch.float32)
    mean, scale = matrix.mean(dim=0), matrix.std(dim=0, unbiased=False).clamp_min(1e-6)
    normalized_train = (matrix - mean) / scale
    thresholds = {"l2_distance_max": float(torch.linalg.vector_norm(normalized_train, dim=1).max().item() * 1.5 + 1e-6), "max_abs_z": float(normalized_train.abs().amax(dim=1).max().item() * 1.5 + 1e-6)}
    torch.manual_seed(seed)
    random.seed(seed)
    model = CoreRuleRanker(len(FEATURE_NAMES), hidden_dim)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    best_state: dict[str, Tensor] | None = None
    best_margin = float("-inf")
    history = []
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
        history.append({"epoch": epoch, "loss": float(loss.item()), **validation})
        if validation["mean_margin"] > best_margin:
            best_margin = validation["mean_margin"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError("professional residual ranker did not produce a checkpoint")
    model.load_state_dict(best_state)
    metrics = {split: _evaluate(model, pairs, mean, scale) for split, pairs in pairs_by_split.items()}
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "professional_residual_rule_ranker.pt"
    torch.save({"schema_version": MODEL_SCHEMA, "model_version": MODEL_VERSION, "state_dict": {key: value.cpu() for key, value in model.state_dict().items()}, "normalization": {"mean": mean.tolist(), "scale": scale.tolist()}, "ood_thresholds": thresholds, "config": {"input_dim": len(FEATURE_NAMES), "hidden_dim": hidden_dim}, "feature_names": list(FEATURE_NAMES), "target_scope": manifest["target_scope"], "teacher_rule_id": manifest["teacher_rule_id"]}, checkpoint)
    metrics_path = _write_json(output_dir / "metrics.json", {"schema_version": MODEL_SCHEMA, "model_version": MODEL_VERSION, "dataset_id": manifest["dataset_id"], "metrics": metrics, "ood_thresholds": thresholds, "gradient_descent": {"optimizer": "AdamW", "epochs": epochs, "learning_rate": learning_rate, "pairwise_loss": "softplus(-(residual_score-abrupt_score))"}, "professional_teacher_rule_count": 1, "human_aesthetic_labels_used": 0, "status": "pilot_narrow_axis_not_general_quality", "created_at": datetime.now(timezone.utc).isoformat()})
    card = output_dir / "MODEL_CARD.md"
    card.write_text(f"# Professional Residual Rule Ranker\n\nStatus: `pilot_narrow_axis_not_general_quality`.\n\nThis PyTorch MLP uses pairwise gradient descent over `{manifest['pair_count']}` verified explosion Residual-off/on pairs. It predicts only relative `explosion/residual_persistence`; it does not judge residual material quality, overall rhythm or global VFX quality.\n\nTest pair accuracy: `{metrics['test']['pair_accuracy']:.4f}` across `{int(metrics['test']['pair_count'])}` held-out pairs. The test set is intentionally small.\n", encoding="utf-8")
    return {"checkpoint": checkpoint, "metrics": metrics_path, "model_card": card}


def rank_batch(checkpoint_path: Path, generation_manifest_path: Path, output_path: Path) -> Path:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    if payload.get("schema_version") != MODEL_SCHEMA or payload.get("target_scope") != {"effect_family": "explosion", "judgment_axis": "residual_persistence"}:
        raise ValueError("checkpoint is not an explosion/residual_persistence model")
    if tuple(payload.get("feature_names") or ()) != FEATURE_NAMES:
        raise ValueError("checkpoint feature order does not match the residual extractor")
    model = CoreRuleRanker(int(payload["config"]["input_dim"]), int(payload["config"]["hidden_dim"]))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    mean, scale = torch.tensor(payload["normalization"]["mean"], dtype=torch.float32), torch.tensor(payload["normalization"]["scale"], dtype=torch.float32)
    limits = payload["ood_thresholds"]
    manifest = _read_json(generation_manifest_path.resolve())
    if manifest.get("capture_protocol") != CAPTURE_PROTOCOL:
        raise ValueError(f"residual ranking requires capture protocol {CAPTURE_PROTOCOL}")
    rows = []
    for candidate in manifest["candidates"]:
        graph = _read_json(_resolve(candidate["graph_path"] if "graph_path" in candidate else candidate["guided_graph_path"]))
        late_start = _non_residual_end_seconds(graph) + 0.05
        features = _capture_features(_resolve(candidate["capture_manifest_path"]), late_start)
        vector = (torch.tensor([features[name] for name in FEATURE_NAMES], dtype=torch.float32) - mean) / scale
        l2, max_abs = float(torch.linalg.vector_norm(vector).item()), float(vector.abs().max().item())
        with torch.inference_mode():
            score = float(model(vector.unsqueeze(0))[0].item())
        rows.append({"candidate_id": candidate["candidate_id"], "graph_id": candidate.get("graph_id") or candidate.get("guided_graph_id"), "residual_persistence_score": score, "late_window_start_seconds": late_start, "distribution": {"in_distribution": l2 <= float(limits["l2_distance_max"]), "l2_distance": l2, "l2_limit": float(limits["l2_distance_max"]), "max_abs_z": max_abs, "max_abs_z_diagnostic_limit": float(limits["max_abs_z"]), "gate": "l2_distance"}, "capture_manifest_path": _resolve(candidate["capture_manifest_path"]).as_posix()})
    rows.sort(key=lambda row: (not row["distribution"]["in_distribution"], -row["residual_persistence_score"], row["candidate_id"]))
    in_distribution_count = sum(row["distribution"]["in_distribution"] for row in rows)
    return _write_json(output_path.resolve(), {"schema_version": "vfx_professional_residual_rule_ranking.v1", "created_at": datetime.now(timezone.utc).isoformat(), "model_path": checkpoint_path.resolve().as_posix(), "model_version": payload["model_version"], "target_scope": payload["target_scope"], "candidate_count": len(rows), "in_distribution_count": in_distribution_count, "ranking": rows, "score_interpretation": "Uncalibrated relative proposal score for explosion/residual_persistence only; not overall quality or residual material quality.", "status": "pass" if rows and in_distribution_count else "blocked_out_of_distribution" if rows else "blocked_no_candidates"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, train and apply the explosion residual-persistence model.")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("prepare-evaluation")
    evaluate.add_argument("--generation-manifest", type=Path, required=True)
    evaluate.add_argument("--output-root", type=Path, required=True)
    build = commands.add_parser("build-dataset")
    build.add_argument("--ablation-manifest", type=Path, required=True)
    build.add_argument("--ablation-report", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--dataset-id", default="professional_residual_rule_training_r001")
    merge = commands.add_parser("merge-datasets")
    merge.add_argument("--dataset-root", type=Path, action="append", required=True)
    merge.add_argument("--output-root", type=Path, required=True)
    merge.add_argument("--dataset-id", default="professional_residual_rule_training_r003_axis_local")
    train = commands.add_parser("train")
    train.add_argument("--dataset-root", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--epochs", type=int, default=300)
    train.add_argument("--learning-rate", type=float, default=0.01)
    train.add_argument("--hidden-dim", type=int, default=12)
    train.add_argument("--seed", type=int, default=20260904)
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
        elif args.command == "merge-datasets":
            paths = merge_datasets(args.dataset_root, args.output_root, args.dataset_id)
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
