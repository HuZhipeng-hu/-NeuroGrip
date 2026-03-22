"""Run the event-onset model runtime controller (MindIR Lite by default, CKPT for debug)."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from event_onset.config import load_event_runtime_config, load_event_training_config
from event_onset.inference import EventPredictor
from event_onset.actuation_mapping import load_and_validate_actuation_map
from event_onset.runtime import EventOnsetController
from runtime.hardware.factory import create_actuator
from scripts.bundle_utils import sha256_file
from scripts.collection_utils import STANDARD_CSV_HEADERS
from shared.event_labels import normalize_event_label_input, public_event_labels, public_event_mapping
from shared.label_modes import get_label_mode_spec
from shared.run_utils import build_run_id, dump_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run event-onset runtime controller")
    parser.add_argument("--config", default="configs/runtime_event_onset.yaml")
    parser.add_argument("--training_config", default=None, help="Override training config used for schema validation.")
    parser.add_argument("--backend", default="lite", choices=["lite", "ckpt"])
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--model_path", default=None, help="MindIR model path for --backend lite")
    parser.add_argument("--model_metadata", default=None, help="Model metadata json path for --backend lite")
    parser.add_argument("--actuation_mapping", default=None, help="Class-to-actuator mapping YAML path.")
    parser.add_argument(
        "--target_db5_keys",
        default=None,
        help=(
            "Comma-separated action keys to override runtime config, "
            "e.g. TENSE_OPEN,V_SIGN,THUMB_UP,WRIST_CW."
        ),
    )
    parser.add_argument("--port", default=None)
    parser.add_argument("--device", default=None, choices=["CPU", "GPU", "Ascend"])
    parser.add_argument("--source_csv", default=None, help="Replay a standardized CSV instead of reading the live device.")
    parser.add_argument("--duration_sec", type=float, default=0.0, help="Optional live duration. 0 means until Ctrl+C.")
    parser.add_argument("--standalone", action="store_true", help="Use standalone actuator mock.")
    parser.add_argument("--session_dir", default=None, help="Directory for startup/session audit artifacts.")
    parser.add_argument("--startup_only", action="store_true", help="Validate startup artifacts and exit before reading the sensor.")
    parser.add_argument(
        "--trace_jsonl",
        action="store_true",
        help="Write per-step inference diagnostics to step_trace_log.jsonl for offline replay/debug.",
    )
    return parser


def _load_standardized_matrix(path: str | Path) -> np.ndarray:
    rows: list[list[float]] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV missing header: {path}")
        for row in reader:
            rows.append([float(row[field]) for field in STANDARD_CSV_HEADERS[:14]])
    if not rows:
        raise ValueError(f"CSV has no rows: {path}")
    matrix = np.asarray(rows, dtype=np.float32)
    if matrix[:, :8].min(initial=0.0) >= 0.0 and matrix[:, :8].max(initial=0.0) > 64.0:
        matrix[:, :8] -= 128.0
    return matrix


def _rows_from_frame(parsed: dict) -> np.ndarray:
    acc = np.asarray(parsed["acc"], dtype=np.float32)
    gyro = np.asarray(parsed["gyro"], dtype=np.float32)
    imu_row = np.concatenate([acc, gyro], axis=0)
    rows = []
    for pack in parsed.get("emg") or []:
        emg = np.asarray(pack[:8], dtype=np.float32)
        if emg.min(initial=0.0) >= 0.0 and emg.max(initial=0.0) > 64.0:
            emg = emg - 128.0
        rows.append(np.concatenate([emg, imu_row], axis=0))
    return np.asarray(rows, dtype=np.float32)


def _validate_runtime_class_contract(
    *,
    model_backend: str,
    expected_class_names: list[str],
    mapping_by_name: dict[str, str],
    model_num_classes: int | None,
    metadata_class_names: list[str] | None,
) -> None:
    normalized_expected = [normalize_event_label_input(name) for name in expected_class_names]

    mapping_keys = sorted(normalize_event_label_input(key) for key in mapping_by_name.keys())
    if mapping_keys != sorted(normalized_expected):
        raise ValueError(
            f"Actuation mapping keys mismatch expected classes. mapping_keys={public_event_labels(mapping_keys)}, "
            f"expected={public_event_labels(sorted(normalized_expected))}"
        )

    if model_num_classes is None:
        raise ValueError("model_num_classes is required for runtime validation.")
    if int(model_num_classes) != len(normalized_expected):
        raise ValueError(
            f"model.num_classes={model_num_classes} mismatches expected labels={len(normalized_expected)} "
            f"({normalized_expected})"
        )

    if metadata_class_names is None:
        if model_backend == "lite":
            raise ValueError("Lite backend requires model metadata with class_names for strict runtime validation.")
        return

    if not metadata_class_names:
        if model_backend == "lite":
            raise ValueError("Lite backend metadata must include non-empty class_names.")
        return
    normalized_metadata = [normalize_event_label_input(name) for name in metadata_class_names]
    if normalized_metadata != normalized_expected:
        raise ValueError(
            "Runtime class order mismatch between config and model metadata: "
            f"config={public_event_labels(normalized_expected)}, metadata={public_event_labels(normalized_metadata)}"
        )


def _validate_release_contract(
    *,
    release_mode: str,
    class_names: list[str],
    mapping_by_name: dict[str, str],
    momentary_action_labels: list[str] | None = None,
) -> None:
    mode = str(release_mode).strip().lower()
    if mode != "command_only":
        return
    normalized = [str(name).strip().upper() for name in class_names]
    if "TENSE_OPEN" not in normalized:
        raise ValueError(
            "release_mode=command_only requires class TENSE_OPEN in runtime label set."
        )
    mapped = normalize_event_label_input(mapping_by_name.get("TENSE_OPEN", ""))
    if mapped != "TENSE_OPEN":
        raise ValueError(
            "release_mode=command_only requires mapping TENSE_OPEN -> TENSE_OPEN."
        )
    if momentary_action_labels:
        raise ValueError(
            "release_mode=command_only does not allow momentary_action_labels "
            "under the frozen latch contract."
        )


def _ensure_file_exists(path: str | Path, *, desc: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{desc} not found: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"{desc} is not a file: {resolved}")
    if resolved.stat().st_size <= 0:
        raise ValueError(f"{desc} is empty: {resolved}")
    return resolved


def _validate_startup_artifacts(
    *,
    model_backend: str,
    checkpoint_path: str | Path,
    model_path: str | Path,
    model_metadata_path: str | Path,
) -> dict[str, str]:
    if model_backend == "ckpt":
        ckpt = _ensure_file_exists(checkpoint_path, desc="Model checkpoint")
        return {"checkpoint_path": str(ckpt)}
    if model_backend == "lite":
        model = _ensure_file_exists(model_path, desc="MindIR model")
        metadata = _ensure_file_exists(model_metadata_path, desc="Model metadata")
        return {"model_path": str(model), "model_metadata_path": str(metadata)}
    raise ValueError(f"Unsupported model backend: {model_backend}")


def _resolve_runtime_session_paths(session_dir: str | Path | None) -> dict[str, Path]:
    if str(session_dir or "").strip():
        base = Path(str(session_dir)).resolve()
        base.mkdir(parents=True, exist_ok=True)
    else:
        base = (CODE_ROOT / "artifacts" / "runtime_sessions" / build_run_id("event_runtime")).resolve()
        base.mkdir(parents=True, exist_ok=True)
    return {
        "session_dir": base,
        "startup_report": base / "startup_report.json",
        "decision_log": base / "decision_log.jsonl",
        "step_trace_log": base / "step_trace_log.jsonl",
        "session_summary": base / "session_summary.json",
    }


def _artifact_record(path: str | Path | None) -> dict[str, object]:
    if path is None:
        return {"path": None, "exists": False}
    resolved = Path(path).resolve()
    record: dict[str, object] = {"path": str(resolved), "exists": bool(resolved.exists())}
    if resolved.exists() and resolved.is_file():
        record["size_bytes"] = int(resolved.stat().st_size)
        record["sha256"] = sha256_file(resolved)
    return record


def _device_diagnostics(device) -> dict[str, object] | None:
    if device is None:
        return None
    stats = dict(getattr(device, "stats", {}) or {})
    diagnostics: dict[str, object] = {
        "type": type(device).__name__,
        "port": getattr(device, "port", None),
        "baudrate": getattr(device, "baudrate", None),
        "connected": bool(device.is_connected()) if hasattr(device, "is_connected") else None,
        "battery_level": getattr(device, "battery_level", None),
        "stats": stats,
    }
    if hasattr(device, "get_fps"):
        try:
            diagnostics["fps"] = float(device.get_fps())
        except Exception:
            diagnostics["fps"] = None
    return diagnostics


def _actuator_diagnostics(actuator) -> dict[str, object]:
    if hasattr(actuator, "get_info"):
        try:
            return dict(actuator.get_info())
        except Exception:
            pass
    return {"type": type(actuator).__name__}


def _append_jsonl(path: str | Path, payload: dict[str, object]) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with open(resolved, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _release_summary_excerpt(path: str | Path) -> tuple[dict[str, object], str | None]:
    record = _artifact_record(path)
    resolved = Path(path).resolve()
    if not resolved.exists():
        return record, None
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        return record, f"Failed to parse release summary {resolved}: {exc}"
    if not isinstance(payload, dict):
        return record, f"Release summary must contain an object payload: {resolved}"
    record["summary"] = {
        "status": payload.get("status"),
        "run_id": payload.get("run_id"),
        "candidate_run_id": payload.get("candidate_run_id"),
    }
    return record, None


def _build_step_trace_payload(
    *,
    step,
    class_names: list[str],
    source_mode: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "step",
        "source_mode": str(source_mode),
        "sample_index": int(step.sample_index),
        "predicted_class_name": public_event_labels([class_names[step.predicted_label]])[0],
        "emitted_class_name": str(step.decision.emitted_class_name),
        "state": str(step.decision.state.name),
        "changed": bool(step.decision.changed),
        "confidence": float(step.confidence),
        "energy": float(step.energy),
        "now_ms": float(step.now_ms),
        "gate_confidence": (
            None if step.gate_confidence is None else float(step.gate_confidence)
        ),
        "command_confidence": (
            None if step.command_confidence is None else float(step.command_confidence)
        ),
        "current_state_confidence": float(step.current_state_confidence),
        "top2_confidence": float(step.top2_confidence),
    }
    if extra:
        payload.update(extra)
    return payload


def _build_runtime_startup_report(
    *,
    args: argparse.Namespace,
    model_backend: str,
    runtime_cfg,
    label_spec,
    mapping_by_name: dict[str, str],
    startup_artifacts: dict[str, str],
    predictor,
    actuator,
    trace_predictions: bool,
    trace_jsonl: bool,
    session_paths: dict[str, Path],
) -> dict[str, object]:
    metadata = getattr(predictor, "metadata", None)
    metadata_summary = None
    if metadata is not None:
        metadata_summary = {
            "model_variant": metadata.model_variant,
            "class_names": list(metadata.class_names),
            "public_class_names": list(metadata.public_class_names),
            "gate_classes": list(metadata.gate_classes),
            "command_classes": list(metadata.command_classes),
            "output_names": list(metadata.output_names),
        }
    warnings: list[str] = []
    if model_backend == "ckpt":
        warnings.append("CKPT backend is for debugging only; Lite is the deployment path.")
    release_summary_record, release_summary_warning = _release_summary_excerpt(CODE_ROOT / "release_summary.json")
    if release_summary_warning is not None:
        warnings.append(release_summary_warning)
    return {
        "status": "ok",
        "generated_at_unix": float(time.time()),
        "session_dir": str(session_paths["session_dir"]),
        "startup_only": bool(args.startup_only),
        "backend": str(model_backend),
        "trace_predictions": bool(trace_predictions),
        "trace_jsonl": bool(trace_jsonl),
        "source_mode": "csv" if str(args.source_csv or "").strip() else "live",
        "source_csv": str(args.source_csv or ""),
        "duration_sec": float(args.duration_sec),
        "config_files": {
            "runtime_config": _artifact_record(args.config),
            "training_config": _artifact_record(runtime_cfg.training_config),
            "actuation_mapping": _artifact_record(runtime_cfg.actuation_mapping_path),
        },
        "model_artifacts": {
            key: _artifact_record(value)
            for key, value in startup_artifacts.items()
        },
        "release_artifacts": {
            "release_summary": release_summary_record,
        },
        "runtime_contract": {
            "class_order": public_event_labels(label_spec.class_names),
            "class_mapping": public_event_mapping(mapping_by_name),
            "release_mode": str(runtime_cfg.runtime.release_mode),
            "momentary_action_labels": list(runtime_cfg.runtime.momentary_action_labels or []),
            "device_target": str(runtime_cfg.device.target),
        },
        "hardware_config": {
            "sensor_mode": str(runtime_cfg.hardware.sensor_mode),
            "actuator_mode": str(runtime_cfg.hardware.actuator_mode),
            "sensor_port": runtime_cfg.hardware.sensor_port,
            "sensor_baudrate": int(runtime_cfg.hardware.sensor_baudrate),
            "actuator_i2c_bus": int(runtime_cfg.hardware.actuator_i2c_bus),
            "actuator_i2c_address": int(runtime_cfg.hardware.actuator_i2c_address),
            "safe_profile_preset": str(runtime_cfg.hardware.safe_profile_preset),
        },
        "metadata_summary": metadata_summary,
        "actuator_info": _actuator_diagnostics(actuator),
        "warnings": warnings,
    }


def _build_runtime_session_summary(
    *,
    session_paths: dict[str, Path],
    startup_report_path: Path,
    source_mode: str,
    trace_predictions: bool,
    trace_jsonl: bool,
    total_steps: int,
    step_trace_count: int,
    transition_counts: dict[str, int],
    last_state: str | None,
    device,
    actuator,
    started_at: float,
    error: Exception | None,
    startup_only: bool,
) -> dict[str, object]:
    status = "startup_only" if startup_only and error is None else ("error" if error is not None else "ok")
    return {
        "status": status,
        "started_at_unix": float(started_at),
        "ended_at_unix": float(time.time()),
        "duration_sec": float(time.time() - started_at),
        "session_dir": str(session_paths["session_dir"]),
        "startup_report": str(startup_report_path),
        "decision_log": str(session_paths["decision_log"]),
        "step_trace_log": (
            str(session_paths["step_trace_log"])
            if bool(trace_jsonl)
            else None
        ),
        "source_mode": str(source_mode),
        "trace_predictions": bool(trace_predictions),
        "trace_jsonl": bool(trace_jsonl),
        "total_steps": int(total_steps),
        "step_trace_count": int(step_trace_count),
        "transition_count": int(sum(int(value) for value in transition_counts.values())),
        "transition_counts": {str(key): int(value) for key, value in transition_counts.items()},
        "last_state": last_state,
        "device_diagnostics": _device_diagnostics(device),
        "actuator_info": _actuator_diagnostics(actuator),
        "error": (
            {
                "type": type(error).__name__,
                "message": str(error),
            }
            if error is not None
            else None
        ),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    logger = logging.getLogger("event_runtime")
    args = build_parser().parse_args()

    runtime_cfg = load_event_runtime_config(args.config)
    model_backend = str(args.backend).strip().lower()
    if args.training_config:
        runtime_cfg.training_config = str(args.training_config)
    if args.checkpoint:
        runtime_cfg.checkpoint_path = args.checkpoint
    if args.model_path:
        runtime_cfg.model_path = args.model_path
    if args.model_metadata:
        runtime_cfg.model_metadata_path = args.model_metadata
    if args.actuation_mapping:
        runtime_cfg.actuation_mapping_path = args.actuation_mapping
    if args.target_db5_keys:
        keys = [item.strip().upper() for item in str(args.target_db5_keys).split(",") if item.strip()]
        if not keys:
            raise ValueError("--target_db5_keys provided but no valid keys parsed.")
        runtime_cfg.data.target_db5_keys = keys
    if args.port:
        runtime_cfg.hardware.sensor_port = args.port
    if args.device:
        runtime_cfg.device.target = args.device
    if args.standalone:
        runtime_cfg.hardware.actuator_mode = "standalone"

    model_cfg, _, _, _ = load_event_training_config(runtime_cfg.training_config)
    label_spec = get_label_mode_spec(runtime_cfg.data.label_mode, runtime_cfg.data.target_db5_keys)
    model_cfg.num_classes = int(len(label_spec.class_names))
    label_to_state, mapping_by_name = load_and_validate_actuation_map(
        runtime_cfg.actuation_mapping_path,
        class_names=label_spec.class_names,
    )
    startup_artifacts = _validate_startup_artifacts(
        model_backend=model_backend,
        checkpoint_path=runtime_cfg.checkpoint_path,
        model_path=runtime_cfg.model_path,
        model_metadata_path=runtime_cfg.model_metadata_path,
    )

    metadata_class_names: list[str] | None = None
    predictor = EventPredictor(
        backend=model_backend,
        model_config=model_cfg,
        device_target=runtime_cfg.device.target,
        checkpoint_path=runtime_cfg.checkpoint_path,
        model_path=runtime_cfg.model_path,
        model_metadata_path=runtime_cfg.model_metadata_path,
    )
    if predictor.metadata is not None:
        metadata_names = predictor.metadata.public_class_names or predictor.metadata.class_names
        if metadata_names:
            metadata_class_names = [str(name).strip().upper() for name in metadata_names]

    _validate_runtime_class_contract(
        model_backend=model_backend,
        expected_class_names=list(label_spec.class_names),
        model_num_classes=int(model_cfg.num_classes),
        mapping_by_name=mapping_by_name,
        metadata_class_names=metadata_class_names,
    )
    _validate_release_contract(
        release_mode=runtime_cfg.runtime.release_mode,
        class_names=list(label_spec.class_names),
        mapping_by_name=mapping_by_name,
        momentary_action_labels=list(runtime_cfg.runtime.momentary_action_labels or []),
    )

    actuator = create_actuator(runtime_cfg.hardware)
    if hasattr(actuator, "connect"):
        if actuator.connect() is False:
            raise RuntimeError("Failed to connect actuator hardware.")

    logger.info(
        "Event runtime started: model_backend=%s device=%s actuation_mapping=%s",
        model_backend,
        runtime_cfg.device.target,
        runtime_cfg.actuation_mapping_path,
    )
    logger.info(
        "Model artifacts: checkpoint=%s model=%s metadata=%s",
        runtime_cfg.checkpoint_path,
        runtime_cfg.model_path,
        runtime_cfg.model_metadata_path,
    )
    logger.info("Class order: %s", public_event_labels(label_spec.class_names))
    logger.info("Class mapping: %s", public_event_mapping(mapping_by_name))
    logger.info("Release mode: %s", runtime_cfg.runtime.release_mode)
    trace_predictions = str(os.getenv("EVENT_RUNTIME_TRACE", "")).strip().lower() in {"1", "true", "yes", "on"}
    trace_jsonl = bool(args.trace_jsonl)
    session_paths = _resolve_runtime_session_paths(args.session_dir)
    total_steps = 0
    step_trace_count = 0
    transition_counts: dict[str, int] = {}
    last_state: str | None = None
    started_at = time.time()
    runtime_error: Exception | None = None
    device = None
    if model_backend == "ckpt":
        logger.warning("CKPT backend is intended for debugging only. Use --backend lite for production deployment.")

    controller = EventOnsetController(
        data_config=runtime_cfg.data,
        inference_config=runtime_cfg.inference,
        runtime_config=runtime_cfg.runtime,
        class_names=label_spec.class_names,
        label_to_state=label_to_state,
        predict_proba=predictor.predict_proba,
        predict_detail=predictor.predict_detail,
        actuator=actuator,
    )

    try:
        startup_report = _build_runtime_startup_report(
            args=args,
            model_backend=model_backend,
            runtime_cfg=runtime_cfg,
            label_spec=label_spec,
            mapping_by_name=mapping_by_name,
            startup_artifacts=startup_artifacts,
            predictor=predictor,
            actuator=actuator,
            trace_predictions=trace_predictions,
            trace_jsonl=trace_jsonl,
            session_paths=session_paths,
        )
        startup_report_path = dump_json(session_paths["startup_report"], startup_report)
        logger.info("Startup report: %s", startup_report_path)
        if args.startup_only:
            logger.info("Startup validation completed successfully; exiting because --startup_only was set.")
            return

        if args.source_csv:
            matrix = _load_standardized_matrix(args.source_csv)
            for step in controller.ingest_rows(matrix):
                total_steps += 1
                step_payload = _build_step_trace_payload(
                    step=step,
                    class_names=list(label_spec.class_names),
                    source_mode="csv",
                )
                if trace_jsonl:
                    _append_jsonl(session_paths["step_trace_log"], step_payload)
                    step_trace_count += 1
                last_state = str(step.decision.state.name)
                if trace_predictions:
                    logger.info(
                        "trace state=%s predicted=%s emitted=%s confidence=%.3f energy=%.3f now_ms=%.1f",
                        step.decision.state.name,
                        label_spec.class_names[step.predicted_label],
                        step.decision.emitted_class_name,
                        step.confidence,
                        step.energy,
                        step.now_ms,
                    )
                if step.decision.changed:
                    transition_counts[step.decision.emitted_class_name] = (
                        int(transition_counts.get(step.decision.emitted_class_name, 0)) + 1
                    )
                    transition_payload = dict(step_payload)
                    transition_payload["kind"] = "transition"
                    _append_jsonl(session_paths["decision_log"], transition_payload)
                    logger.info(
                        "state=%s class=%s confidence=%.3f energy=%.3f now_ms=%.1f",
                        step.decision.state.name,
                        step.decision.emitted_class_name,
                        step.confidence,
                        step.energy,
                        step.now_ms,
                    )
            return

        from scripts.emg_armband import Device

        device = Device(
            port=runtime_cfg.hardware.sensor_port or "COM4",
            baudrate=runtime_cfg.hardware.sensor_baudrate,
            timeout=0.5,
        )
        if device.connect() is False:
            raise RuntimeError(f"Failed to connect sensor device on port={runtime_cfg.hardware.sensor_port or 'COM4'}")
        start = time.monotonic()
        try:
            while True:
                if args.duration_sec > 0 and (time.monotonic() - start) >= args.duration_sec:
                    break
                frames = device.read_frames()
                if not frames:
                    time.sleep(float(runtime_cfg.runtime.poll_interval_ms) / 1000.0)
                    continue
                for parsed in frames:
                    rows = _rows_from_frame(parsed)
                    for step in controller.ingest_rows(rows):
                        total_steps += 1
                        extra = {
                            "battery_level": getattr(device, "battery_level", None),
                            "device_stats": dict(getattr(device, "stats", {}) or {}),
                        }
                        step_payload = _build_step_trace_payload(
                            step=step,
                            class_names=list(label_spec.class_names),
                            source_mode="live",
                            extra=extra,
                        )
                        if trace_jsonl:
                            _append_jsonl(session_paths["step_trace_log"], step_payload)
                            step_trace_count += 1
                        last_state = str(step.decision.state.name)
                        if trace_predictions:
                            logger.info(
                                "trace state=%s predicted=%s emitted=%s confidence=%.3f energy=%.3f now_ms=%.1f",
                                step.decision.state.name,
                                label_spec.class_names[step.predicted_label],
                                step.decision.emitted_class_name,
                                step.confidence,
                                step.energy,
                                step.now_ms,
                            )
                        if step.decision.changed:
                            transition_counts[step.decision.emitted_class_name] = (
                                int(transition_counts.get(step.decision.emitted_class_name, 0)) + 1
                            )
                            transition_payload = dict(step_payload)
                            transition_payload["kind"] = "transition"
                            _append_jsonl(session_paths["decision_log"], transition_payload)
                            logger.info(
                                "state=%s class=%s confidence=%.3f energy=%.3f now_ms=%.1f",
                                step.decision.state.name,
                                step.decision.emitted_class_name,
                                step.confidence,
                                step.energy,
                                step.now_ms,
                            )
        finally:
            device.disconnect()
    except Exception as exc:
        runtime_error = exc
        raise
    finally:
        startup_report_path = session_paths["startup_report"]
        summary = _build_runtime_session_summary(
            session_paths=session_paths,
            startup_report_path=startup_report_path,
            source_mode="csv" if str(args.source_csv or "").strip() else "live",
            trace_predictions=trace_predictions,
            trace_jsonl=trace_jsonl,
            total_steps=total_steps,
            step_trace_count=step_trace_count,
            transition_counts=transition_counts,
            last_state=last_state,
            device=device,
            actuator=actuator,
            started_at=started_at,
            error=runtime_error,
            startup_only=bool(args.startup_only),
        )
        summary_path = dump_json(session_paths["session_summary"], summary)
        logger.info("Runtime session summary: %s", summary_path)
        if hasattr(actuator, "disconnect"):
            actuator.disconnect()


if __name__ == "__main__":
    main()
