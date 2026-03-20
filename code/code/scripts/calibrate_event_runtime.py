"""Collect a short wearer calibration set and export a drop-in runtime config."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from event_onset.actuation_mapping import load_and_validate_actuation_map
from event_onset.config import load_event_runtime_config, load_event_training_config
from event_onset.dataset import EventClipDatasetLoader
from event_onset.inference import EventPredictor
from shared.event_labels import public_event_mapping
from shared.label_modes import get_label_mode_spec
from shared.run_utils import copy_config_snapshot, dump_json, ensure_run_dir
from scripts.tune_event_runtime_thresholds import (
    _evaluate_combo,
    _parse_float_tokens,
    _parse_int_tokens,
    _rank_key,
    _validate_runtime_class_contract,
    _write_runtime_config,
)

DEFAULT_TARGET_KEYS = "TENSE_OPEN,THUMB_UP,WRIST_CW"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Short runtime calibration for the demo3 release path.")
    parser.add_argument("--run_root", default="artifacts/runs")
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--candidate_run_id", required=True)
    parser.add_argument("--training_config", default="configs/training_event_onset.yaml")
    parser.add_argument("--runtime_config", default="configs/runtime_event_onset.yaml")
    parser.add_argument("--data_dir", default="../data")
    parser.add_argument("--calibration_data_dir", default=None)
    parser.add_argument("--calibration_manifest", default=None)
    parser.add_argument("--backend", default="lite", choices=["ckpt", "lite"])
    parser.add_argument("--device_target", default="CPU", choices=["CPU", "GPU", "Ascend"])
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--model_path", default=None)
    parser.add_argument("--model_metadata", default=None)
    parser.add_argument("--actuation_mapping", default=None)
    parser.add_argument("--target_db5_keys", default=DEFAULT_TARGET_KEYS)
    parser.add_argument("--user_id", default="demo_user")
    parser.add_argument("--session_id", default="")
    parser.add_argument("--device_id", default="armband01")
    parser.add_argument("--wearing_state", default="normal")
    parser.add_argument("--port", default=None)
    parser.add_argument("--baudrate", type=int, default=None)
    parser.add_argument("--skip_collect", action="store_true")
    parser.add_argument("--continue_clip_count", type=int, default=5)
    parser.add_argument("--continue_duration_sec", type=float, default=4.0)
    parser.add_argument("--command_duration_sec", type=float, default=30.0)
    parser.add_argument("--command_clip_duration_sec", type=float, default=3.0)
    parser.add_argument("--pre_roll_ms", type=int, default=500)
    parser.add_argument("--confidence_thresholds", default="0.82,0.86,0.90")
    parser.add_argument("--gate_confidence_thresholds", default="0.82,0.86,0.90")
    parser.add_argument("--command_confidence_thresholds", default="0.74,0.78,0.82")
    parser.add_argument("--activation_margins", default="0.10,0.14,0.18")
    parser.add_argument("--vote_windows", default="3,5")
    parser.add_argument("--vote_min_counts", default="2,3")
    parser.add_argument("--switch_confidence_boosts", default="0.08,0.12")
    parser.add_argument("--output_runtime_config", default=None)
    parser.add_argument("--output_json", default=None)
    parser.add_argument("--compare_json", default=None)
    return parser


def _format_cmd(cmd: list[str]) -> str:
    return " ".join(str(item) if " " not in str(item) else f'"{item}"' for item in cmd)


def _run_checked(stage: str, cmd: list[str]) -> None:
    print(f"[CALIBRATE] {stage} -> {_format_cmd(cmd)}", flush=True)
    completed = subprocess.run(cmd, cwd=str(CODE_ROOT), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{stage} failed with rc={completed.returncode}")


def _parse_target_keys(raw: str) -> list[str]:
    keys = [item.strip().upper() for item in str(raw).split(",") if item.strip()]
    if not keys:
        raise ValueError("target_db5_keys must contain at least one action key")
    return keys


def _collect_short_calibration(args: argparse.Namespace, *, calibration_data_dir: Path, manifest_path: Path) -> dict:
    runtime_cfg = load_event_runtime_config(args.runtime_config)
    sensor_port = str(args.port or runtime_cfg.hardware.sensor_port or "COM4")
    sensor_baudrate = int(args.baudrate or runtime_cfg.hardware.sensor_baudrate or 115200)
    session_id = str(args.session_id or args.run_id)
    target_keys = _parse_target_keys(args.target_db5_keys)
    command_reports: list[str] = []

    for index in range(int(args.continue_clip_count)):
        cmd = [
            sys.executable,
            "scripts/collect_event_data.py",
            "--data_dir",
            str(calibration_data_dir),
            "--recordings_manifest",
            str(manifest_path.name),
            "--target_state",
            "CONTINUE",
            "--start_state",
            "CONTINUE",
            "--capture_mode",
            "event_onset",
            "--user_id",
            str(args.user_id),
            "--session_id",
            session_id,
            "--device_id",
            str(args.device_id),
            "--wearing_state",
            str(args.wearing_state),
            "--duration_sec",
            str(float(args.continue_duration_sec)),
            "--pre_roll_ms",
            "400",
            "--port",
            sensor_port,
            "--baudrate",
            str(sensor_baudrate),
        ]
        _run_checked(f"collect_continue_{index + 1}", cmd)

    for target_state in target_keys:
        report_path = calibration_data_dir / f"{target_state.lower()}_slice_report.json"
        cmd = [
            sys.executable,
            "scripts/collect_event_data_continuous.py",
            "--config",
            str(args.training_config),
            "--data_dir",
            str(calibration_data_dir),
            "--recordings_manifest",
            str(manifest_path.name),
            "--target_state",
            str(target_state),
            "--start_state",
            "CONTINUE",
            "--capture_mode",
            "event_onset",
            "--user_id",
            str(args.user_id),
            "--session_id",
            session_id,
            "--device_id",
            str(args.device_id),
            "--wearing_state",
            str(args.wearing_state),
            "--duration_sec",
            str(float(args.command_duration_sec)),
            "--clip_duration_sec",
            str(float(args.command_clip_duration_sec)),
            "--pre_roll_ms",
            str(int(args.pre_roll_ms)),
            "--min_active_sec",
            "0.28",
            "--min_gap_sec",
            "1.0",
            "--smooth_ms",
            "80",
            "--q_low",
            "0.20",
            "--q_high",
            "0.90",
            "--threshold_alpha",
            "0.35",
            "--keep_quality",
            "pass,warn",
            "--save_stream_csv",
            "--min_rows_gate",
            "10000",
            "--min_candidates_gate",
            "2",
            "--min_accepted_gate",
            "2",
            "--enforce_collection_gate",
            "--report_json",
            str(report_path),
            "--port",
            sensor_port,
            "--baudrate",
            str(sensor_baudrate),
        ]
        _run_checked(f"collect_{target_state.lower()}", cmd)
        command_reports.append(str(report_path))

    return {
        "session_id": session_id,
        "sensor_port": sensor_port,
        "sensor_baudrate": sensor_baudrate,
        "command_reports": command_reports,
    }


def _resolve_candidate_artifacts(args: argparse.Namespace) -> dict[str, str]:
    runtime_cfg = load_event_runtime_config(args.runtime_config)
    candidate_run_dir = Path(args.run_root) / str(args.candidate_run_id)
    checkpoint = str(args.checkpoint or (candidate_run_dir / "checkpoints" / "event_onset_best.ckpt"))
    model_path = str(args.model_path or runtime_cfg.model_path)
    model_metadata = str(args.model_metadata or runtime_cfg.model_metadata_path)
    return {
        "candidate_run_dir": str(candidate_run_dir),
        "checkpoint": checkpoint,
        "model_path": model_path,
        "model_metadata": model_metadata,
    }


def _collect_calibration_clips(
    *,
    calibration_data_dir: Path,
    manifest_path: Path,
    training_config: str,
    target_keys: list[str],
) -> tuple[list[tuple[int, int, object]], dict[str, int], dict]:
    _, data_cfg, _, _ = load_event_training_config(training_config)
    data_cfg.target_db5_keys = list(target_keys)
    label_spec = get_label_mode_spec(data_cfg.label_mode, data_cfg.target_db5_keys)
    class_names = [str(name).strip().upper() for name in label_spec.class_names]
    class_to_idx = {name: int(idx) for idx, name in enumerate(class_names)}

    loader = EventClipDatasetLoader(
        str(calibration_data_dir),
        data_cfg,
        recordings_manifest_path=str(manifest_path),
    )
    clips: list[tuple[int, int, object]] = []
    clip_counts = {name: 0 for name in class_names}
    for start_state, target_state, matrix, _metadata in loader.iter_clips():
        start_name = str(start_state).strip().upper()
        target_name = str(target_state).strip().upper()
        start_label = int(class_to_idx[start_name])
        target_label = int(class_to_idx[target_name])
        clips.append((start_label, target_label, matrix[:, :14]))
        clip_counts[target_name] = int(clip_counts.get(target_name, 0) + 1)

    if not clips:
        raise RuntimeError("Calibration collection produced no usable clips.")

    try:
        loader.load_all_with_sources(return_metadata=False)
        quality_report = loader.get_quality_report()
    except Exception as exc:
        quality_report = {"status": "partial", "reason": str(exc)}

    return clips, clip_counts, quality_report


def _evaluate_runtime_on_clips(
    *,
    clips: list[tuple[int, int, object]],
    runtime_config_path: Path,
    training_config: str,
    target_keys: list[str],
    checkpoint: str,
    model_path: str,
    model_metadata: str,
    backend: str,
    device_target: str,
    actuation_mapping_path: str | None,
) -> tuple[dict, dict]:
    model_cfg, data_cfg, _, _ = load_event_training_config(training_config)
    data_cfg.target_db5_keys = list(target_keys)
    runtime_cfg = load_event_runtime_config(runtime_config_path)
    runtime_cfg.data.target_db5_keys = list(target_keys)
    if actuation_mapping_path:
        runtime_cfg.actuation_mapping_path = str(actuation_mapping_path)
    if backend == "ckpt":
        runtime_cfg.checkpoint_path = str(checkpoint)
    else:
        runtime_cfg.model_path = str(model_path)
        runtime_cfg.model_metadata_path = str(model_metadata)

    label_spec = get_label_mode_spec(data_cfg.label_mode, data_cfg.target_db5_keys)
    model_cfg.num_classes = int(len(label_spec.class_names))
    label_to_state, mapping_by_name = load_and_validate_actuation_map(
        runtime_cfg.actuation_mapping_path,
        class_names=label_spec.class_names,
    )
    predictor = EventPredictor(
        backend=str(backend),
        model_config=model_cfg,
        device_target=str(device_target),
        checkpoint_path=runtime_cfg.checkpoint_path,
        model_path=runtime_cfg.model_path,
        model_metadata_path=runtime_cfg.model_metadata_path,
    )
    _validate_runtime_class_contract(
        backend=str(backend),
        expected_class_names=list(label_spec.class_names),
        model_num_classes=int(model_cfg.num_classes),
        mapping_by_name=mapping_by_name,
        metadata=predictor.metadata,
    )
    params = {
        "confidence_threshold": float(runtime_cfg.inference.confidence_threshold),
        "gate_confidence_threshold": float(
            runtime_cfg.inference.gate_confidence_threshold
            if runtime_cfg.inference.gate_confidence_threshold is not None
            else runtime_cfg.inference.confidence_threshold
        ),
        "command_confidence_threshold": float(
            runtime_cfg.inference.command_confidence_threshold
            if runtime_cfg.inference.command_confidence_threshold is not None
            else runtime_cfg.inference.confidence_threshold
        ),
        "activation_margin_threshold": float(runtime_cfg.inference.activation_margin_threshold),
        "vote_window": int(runtime_cfg.inference.vote_window),
        "vote_min_count": int(runtime_cfg.inference.vote_min_count),
        "switch_confidence_boost": float(runtime_cfg.inference.switch_confidence_boost),
    }
    metrics = _evaluate_combo(
        clips=clips,
        class_names=list(label_spec.class_names),
        label_to_state=label_to_state,
        data_cfg=runtime_cfg.data,
        runtime_cfg=runtime_cfg,
        predict_proba=predictor.predict_proba,
        predict_detail=predictor.predict_detail,
        params=params,
    )
    return metrics, {
        "class_names": list(label_spec.class_names),
        "mapping": public_event_mapping(mapping_by_name),
        "params": dict(params),
    }


def _run_threshold_search(
    *,
    clips: list[tuple[int, int, object]],
    runtime_config_path: Path,
    training_config: str,
    target_keys: list[str],
    checkpoint: str,
    model_path: str,
    model_metadata: str,
    backend: str,
    device_target: str,
    actuation_mapping_path: str | None,
    args: argparse.Namespace,
) -> tuple[dict, list[dict], dict]:
    model_cfg, data_cfg, _, _ = load_event_training_config(training_config)
    data_cfg.target_db5_keys = list(target_keys)
    runtime_cfg = load_event_runtime_config(runtime_config_path)
    runtime_cfg.data.target_db5_keys = list(target_keys)
    if actuation_mapping_path:
        runtime_cfg.actuation_mapping_path = str(actuation_mapping_path)
    if backend == "ckpt":
        runtime_cfg.checkpoint_path = str(checkpoint)
    else:
        runtime_cfg.model_path = str(model_path)
        runtime_cfg.model_metadata_path = str(model_metadata)

    label_spec = get_label_mode_spec(data_cfg.label_mode, data_cfg.target_db5_keys)
    model_cfg.num_classes = int(len(label_spec.class_names))
    label_to_state, mapping_by_name = load_and_validate_actuation_map(
        runtime_cfg.actuation_mapping_path,
        class_names=label_spec.class_names,
    )
    predictor = EventPredictor(
        backend=str(backend),
        model_config=model_cfg,
        device_target=str(device_target),
        checkpoint_path=runtime_cfg.checkpoint_path,
        model_path=runtime_cfg.model_path,
        model_metadata_path=runtime_cfg.model_metadata_path,
    )
    _validate_runtime_class_contract(
        backend=str(backend),
        expected_class_names=list(label_spec.class_names),
        model_num_classes=int(model_cfg.num_classes),
        mapping_by_name=mapping_by_name,
        metadata=predictor.metadata,
    )

    confs = _parse_float_tokens(args.confidence_thresholds, name="--confidence_thresholds")
    gate_confs = _parse_float_tokens(args.gate_confidence_thresholds, name="--gate_confidence_thresholds")
    command_confs = _parse_float_tokens(args.command_confidence_thresholds, name="--command_confidence_thresholds")
    margins = _parse_float_tokens(args.activation_margins, name="--activation_margins")
    vote_windows = _parse_int_tokens(args.vote_windows, name="--vote_windows")
    vote_mins = _parse_int_tokens(args.vote_min_counts, name="--vote_min_counts")
    boosts = _parse_float_tokens(args.switch_confidence_boosts, name="--switch_confidence_boosts")

    rows: list[dict] = []
    for conf in confs:
        for gate_conf in gate_confs:
            for command_conf in command_confs:
                for margin in margins:
                    for vote_window in vote_windows:
                        for vote_min in vote_mins:
                            for boost in boosts:
                                params = {
                                    "confidence_threshold": float(conf),
                                    "gate_confidence_threshold": float(gate_conf),
                                    "command_confidence_threshold": float(command_conf),
                                    "activation_margin_threshold": float(margin),
                                    "vote_window": int(vote_window),
                                    "vote_min_count": int(vote_min),
                                    "switch_confidence_boost": float(boost),
                                }
                                metrics = _evaluate_combo(
                                    clips=clips,
                                    class_names=list(label_spec.class_names),
                                    label_to_state=label_to_state,
                                    data_cfg=runtime_cfg.data,
                                    runtime_cfg=runtime_cfg,
                                    predict_proba=predictor.predict_proba,
                                    predict_detail=predictor.predict_detail,
                                    params=params,
                                )
                                row = dict(params)
                                row.update(metrics)
                                rows.append(row)

    if not rows:
        raise RuntimeError("Calibration threshold search produced no candidate rows.")

    ranked = sorted(rows, key=_rank_key, reverse=True)
    return dict(ranked[0]), ranked, {"mapping": public_event_mapping(mapping_by_name)}


def _copy_runtime_config(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)


def _build_compare_report(*, before: dict, after: dict, selected_source: str, selected_runtime_config: str) -> dict:
    return {
        "rank_rule": "command_success_rate desc, false_trigger_rate asc, false_release_rate asc",
        "before": dict(before),
        "after": dict(after),
        "delta": {
            "command_success_rate": float(after["command_success_rate"]) - float(before["command_success_rate"]),
            "false_trigger_rate": float(after["false_trigger_rate"]) - float(before["false_trigger_rate"]),
            "false_release_rate": float(after["false_release_rate"]) - float(before["false_release_rate"]),
        },
        "selected_source": str(selected_source),
        "selected_runtime_config": str(selected_runtime_config),
    }


def _choose_runtime_source(*, before: dict, after: dict) -> str:
    return "tuned" if _rank_key(after) > _rank_key(before) else "default"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("event_runtime_calibration")
    args = build_parser().parse_args()

    run_id, run_dir = ensure_run_dir(args.run_root, args.run_id, default_tag="event_runtime_calibration")
    args.run_id = run_id
    copy_config_snapshot(args.training_config, run_dir / "config_snapshots" / Path(args.training_config).name)
    copy_config_snapshot(args.runtime_config, run_dir / "config_snapshots" / Path(args.runtime_config).name)

    calibration_data_dir = (
        Path(str(args.calibration_data_dir)).resolve()
        if str(args.calibration_data_dir or "").strip()
        else (run_dir / "calibration_data").resolve()
    )
    calibration_data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = (
        Path(str(args.calibration_manifest)).resolve()
        if str(args.calibration_manifest or "").strip()
        else (calibration_data_dir / "recordings_manifest.csv").resolve()
    )

    collection_summary = {"status": "skipped"} if args.skip_collect else _collect_short_calibration(
        args,
        calibration_data_dir=calibration_data_dir,
        manifest_path=manifest_path,
    )

    target_keys = _parse_target_keys(args.target_db5_keys)
    candidate_artifacts = _resolve_candidate_artifacts(args)
    clips, clip_counts, quality_report = _collect_calibration_clips(
        calibration_data_dir=calibration_data_dir,
        manifest_path=manifest_path,
        training_config=args.training_config,
        target_keys=target_keys,
    )
    quality_report_path = run_dir / "calibration_quality_report.json"
    dump_json(quality_report_path, quality_report)

    runtime_config_path = Path(args.runtime_config).resolve()
    before_metrics, before_context = _evaluate_runtime_on_clips(
        clips=clips,
        runtime_config_path=runtime_config_path,
        training_config=args.training_config,
        target_keys=target_keys,
        checkpoint=candidate_artifacts["checkpoint"],
        model_path=candidate_artifacts["model_path"],
        model_metadata=candidate_artifacts["model_metadata"],
        backend=str(args.backend),
        device_target=str(args.device_target),
        actuation_mapping_path=args.actuation_mapping,
    )
    best_row, ranked_rows, tuning_context = _run_threshold_search(
        clips=clips,
        runtime_config_path=runtime_config_path,
        training_config=args.training_config,
        target_keys=target_keys,
        checkpoint=candidate_artifacts["checkpoint"],
        model_path=candidate_artifacts["model_path"],
        model_metadata=candidate_artifacts["model_metadata"],
        backend=str(args.backend),
        device_target=str(args.device_target),
        actuation_mapping_path=args.actuation_mapping,
        args=args,
    )

    tuned_runtime_path = run_dir / "evaluation" / "runtime_event_onset_calibration_tuned.yaml"
    _write_runtime_config(
        source_runtime_config=runtime_config_path,
        best_row=best_row,
        output_path=tuned_runtime_path,
    )
    after_metrics, _after_context = _evaluate_runtime_on_clips(
        clips=clips,
        runtime_config_path=tuned_runtime_path,
        training_config=args.training_config,
        target_keys=target_keys,
        checkpoint=candidate_artifacts["checkpoint"],
        model_path=candidate_artifacts["model_path"],
        model_metadata=candidate_artifacts["model_metadata"],
        backend=str(args.backend),
        device_target=str(args.device_target),
        actuation_mapping_path=args.actuation_mapping,
    )

    final_runtime_path = (
        Path(str(args.output_runtime_config)).resolve()
        if str(args.output_runtime_config or "").strip()
        else (run_dir / "runtime_event_onset_calibrated.yaml").resolve()
    )
    selected_source = _choose_runtime_source(before=before_metrics, after=after_metrics)
    if selected_source == "tuned":
        _copy_runtime_config(tuned_runtime_path, final_runtime_path)
    else:
        _copy_runtime_config(runtime_config_path, final_runtime_path)

    compare_report = _build_compare_report(
        before=before_metrics,
        after=after_metrics,
        selected_source=selected_source,
        selected_runtime_config=str(final_runtime_path),
    )
    compare_json = (
        Path(str(args.compare_json)).resolve()
        if str(args.compare_json or "").strip()
        else (run_dir / "calibration_compare_report.json")
    )
    dump_json(compare_json, compare_report)

    output_json = (
        Path(str(args.output_json)).resolve()
        if str(args.output_json or "").strip()
        else (run_dir / "calibration_summary.json")
    )
    summary = {
        "status": "ok",
        "run_id": run_id,
        "candidate_run_id": str(args.candidate_run_id),
        "candidate_run_dir": candidate_artifacts["candidate_run_dir"],
        "backend": str(args.backend),
        "device_target": str(args.device_target),
        "training_config": str(Path(args.training_config).resolve()),
        "runtime_config": str(runtime_config_path),
        "selected_runtime_config": str(final_runtime_path),
        "selected_runtime_source": str(selected_source),
        "calibration_data_dir": str(calibration_data_dir),
        "calibration_manifest": str(manifest_path),
        "clip_counts": dict(clip_counts),
        "target_db5_keys": list(target_keys),
        "mapping": dict(tuning_context["mapping"]),
        "collection": collection_summary,
        "quality_report_path": str(quality_report_path),
        "before_metrics": dict(before_metrics),
        "after_metrics": dict(after_metrics),
        "best_threshold_row": dict(best_row),
        "search_space_rows": int(len(ranked_rows)),
        "compare_report": str(compare_json),
        "calibration_protocol": {
            "continue_clip_count": int(args.continue_clip_count),
            "continue_duration_sec": float(args.continue_duration_sec),
            "command_duration_sec": float(args.command_duration_sec),
            "command_clip_duration_sec": float(args.command_clip_duration_sec),
            "pre_roll_ms": int(args.pre_roll_ms),
        },
        "notes": [
            "Calibration updates runtime thresholds only. Model weights are unchanged.",
            "Calibration data is stored separately from the main training manifest.",
        ],
    }
    dump_json(output_json, summary)
    logger.info("calibration_summary=%s", output_json)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
