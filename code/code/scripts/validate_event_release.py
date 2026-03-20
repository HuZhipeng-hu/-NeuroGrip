"""Validate the frozen event release path from checkpoint to live prosthesis smoke."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from event_onset.actuation_mapping import load_and_validate_actuation_map
from event_onset.config import load_event_runtime_config, load_event_training_config
from event_onset.inference import EventPredictor
from event_onset.runtime import EventOnsetController
from runtime.hardware.factory import create_actuator
from scripts.run_event_runtime import _rows_from_frame, _validate_release_contract, _validate_startup_artifacts
from shared.event_labels import public_event_mapping
from shared.label_modes import get_label_mode_spec
from shared.run_utils import copy_config_snapshot, dump_json, ensure_run_dir

DEFAULT_TARGET_KEYS = "TENSE_OPEN,THUMB_UP,WRIST_CW"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Release validation for the frozen demo3 path.")
    parser.add_argument("--run_root", default="artifacts/runs")
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--candidate_run_id", required=True)
    parser.add_argument("--training_config", default="configs/training_event_onset.yaml")
    parser.add_argument("--conversion_config", default="configs/conversion_event_onset.yaml")
    parser.add_argument("--runtime_config", default="configs/runtime_event_onset.yaml")
    parser.add_argument("--data_dir", default="../data")
    parser.add_argument("--recordings_manifest", default=None)
    parser.add_argument("--split_manifest", default=None)
    parser.add_argument("--target_db5_keys", default=DEFAULT_TARGET_KEYS)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--convert_device_target", default="CPU", choices=["CPU", "GPU", "Ascend"])
    parser.add_argument("--eval_device_target", default="CPU", choices=["CPU", "GPU", "Ascend"])
    parser.add_argument("--live_backend", default="lite", choices=["lite", "ckpt"])
    parser.add_argument("--port", default=None)
    parser.add_argument("--standalone", action="store_true")
    parser.add_argument("--skip_live_smoke", action="store_true")
    parser.add_argument("--action_trials", type=int, default=5)
    parser.add_argument("--continue_hold_sec", type=float, default=10.0)
    parser.add_argument("--trial_timeout_sec", type=float, default=6.0)
    parser.add_argument("--output_json", default=None)
    return parser


def _format_cmd(cmd: list[str]) -> str:
    return " ".join(str(item) if " " not in str(item) else f'"{item}"' for item in cmd)


def _run_checked(stage: str, cmd: list[str]) -> None:
    print(f"[RELEASE] {stage} -> {_format_cmd(cmd)}", flush=True)
    completed = subprocess.run(cmd, cwd=str(CODE_ROOT), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{stage} failed with rc={completed.returncode}")


def _parse_target_keys(raw: str) -> list[str]:
    keys = [item.strip().upper() for item in str(raw).split(",") if item.strip()]
    if not keys:
        raise ValueError("target_db5_keys must contain at least one action key")
    return keys


def _candidate_checkpoint(args: argparse.Namespace) -> Path:
    if str(args.checkpoint or "").strip():
        return Path(str(args.checkpoint)).resolve()
    return (Path(args.run_root) / str(args.candidate_run_id) / "checkpoints" / "event_onset_best.ckpt").resolve()


def _build_eval_cmd(
    *,
    args: argparse.Namespace,
    output_json: Path,
    backend: str,
    checkpoint: Path,
    model_path: Path | None = None,
    model_metadata: Path | None = None,
) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/evaluate_event_demo_control.py",
        "--run_root",
        str(args.run_root),
        "--run_id",
        str(args.candidate_run_id),
        "--training_config",
        str(args.training_config),
        "--runtime_config",
        str(args.runtime_config),
        "--data_dir",
        str(args.data_dir),
        "--target_db5_keys",
        str(args.target_db5_keys),
        "--backend",
        str(backend),
        "--device_target",
        str(args.eval_device_target),
        "--output_json",
        str(output_json),
    ]
    if str(args.recordings_manifest or "").strip():
        cmd.extend(["--recordings_manifest", str(args.recordings_manifest)])
    if str(args.split_manifest or "").strip():
        cmd.extend(["--split_manifest", str(args.split_manifest)])
    if backend == "ckpt":
        cmd.extend(["--checkpoint", str(checkpoint)])
    else:
        if model_path is None or model_metadata is None:
            raise ValueError("lite evaluation requires model_path and model_metadata")
        cmd.extend(["--model_path", str(model_path), "--model_metadata", str(model_metadata)])
    return cmd


def _build_parity_summary(*, ckpt_summary: dict, lite_summary: dict) -> dict:
    thresholds = {
        "command_success_rate": 0.05,
        "false_trigger_rate": 0.05,
        "false_release_rate": 0.02,
        "event_action_accuracy": 0.02,
    }
    deltas = {
        metric: abs(float(ckpt_summary.get(metric, 0.0)) - float(lite_summary.get(metric, 0.0)))
        for metric in thresholds
    }
    passes = {metric: bool(deltas[metric] <= thresholds[metric]) for metric in thresholds}
    return {
        "thresholds": thresholds,
        "deltas": deltas,
        "passes": passes,
        "passed": bool(all(passes.values())),
    }


def _prompt_yes_no(message: str) -> bool:
    try:
        raw = input(message).strip().lower()
    except EOFError:
        return False
    return raw in {"y", "yes"}


def _build_live_components(
    *,
    args: argparse.Namespace,
    checkpoint: Path,
    model_path: Path,
    model_metadata: Path,
) -> tuple[EventOnsetController, object, object, list[str], dict[int, object]]:
    runtime_cfg = load_event_runtime_config(args.runtime_config)
    runtime_cfg.data.target_db5_keys = _parse_target_keys(args.target_db5_keys)
    if args.port:
        runtime_cfg.hardware.sensor_port = str(args.port)
    if args.standalone:
        runtime_cfg.hardware.actuator_mode = "standalone"

    if args.live_backend == "ckpt":
        runtime_cfg.checkpoint_path = str(checkpoint)
    else:
        runtime_cfg.model_path = str(model_path)
        runtime_cfg.model_metadata_path = str(model_metadata)

    model_cfg, _, _, _ = load_event_training_config(args.training_config)
    label_spec = get_label_mode_spec(runtime_cfg.data.label_mode, runtime_cfg.data.target_db5_keys)
    model_cfg.num_classes = int(len(label_spec.class_names))
    label_to_state, mapping_by_name = load_and_validate_actuation_map(
        runtime_cfg.actuation_mapping_path,
        class_names=label_spec.class_names,
    )
    _validate_startup_artifacts(
        model_backend=str(args.live_backend),
        checkpoint_path=runtime_cfg.checkpoint_path,
        model_path=runtime_cfg.model_path,
        model_metadata_path=runtime_cfg.model_metadata_path,
    )
    _validate_release_contract(
        release_mode=runtime_cfg.runtime.release_mode,
        class_names=list(label_spec.class_names),
        mapping_by_name=mapping_by_name,
    )
    predictor = EventPredictor(
        backend=str(args.live_backend),
        model_config=model_cfg,
        device_target=str(args.eval_device_target),
        checkpoint_path=runtime_cfg.checkpoint_path,
        model_path=runtime_cfg.model_path,
        model_metadata_path=runtime_cfg.model_metadata_path,
    )
    actuator = create_actuator(runtime_cfg.hardware)
    if hasattr(actuator, "connect"):
        actuator.connect()
    from scripts.emg_armband import Device

    device = Device(
        port=runtime_cfg.hardware.sensor_port or "COM4",
        baudrate=int(runtime_cfg.hardware.sensor_baudrate),
        timeout=0.5,
    )
    device.connect()
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
    return controller, device, actuator, list(label_spec.class_names), label_to_state


def _run_action_trial(
    *,
    controller: EventOnsetController,
    device,
    expected_label: str,
    trial_timeout_sec: float,
    trial_index: int,
) -> dict:
    input(f"[LIVE] Trial {trial_index}: perform {expected_label}. Press Enter to start.")
    start = time.monotonic()
    transitions: list[dict] = []
    matched = False
    while (time.monotonic() - start) < float(trial_timeout_sec):
        frames = device.read_frames()
        if not frames:
            time.sleep(0.01)
            continue
        for parsed in frames:
            rows = _rows_from_frame(parsed)
            for step in controller.ingest_rows(rows):
                if not step.decision.changed:
                    continue
                transition = {
                    "elapsed_sec": round(float(time.monotonic() - start), 3),
                    "emitted_class_name": str(step.decision.emitted_class_name),
                    "confidence": round(float(step.confidence), 4),
                    "energy": round(float(step.energy), 4),
                }
                transitions.append(transition)
                if str(step.decision.emitted_class_name).strip().upper() == str(expected_label).strip().upper():
                    matched = True
                    break
            if matched:
                break
        if matched:
            break
    operator_confirmed = True if hasattr(controller.actuator, "get_info") and controller.actuator.get_info().get("type") == "StandaloneActuator" else _prompt_yes_no(
        f"[LIVE] Did the prosthesis execute {expected_label} correctly? [y/N]: "
    )
    return {
        "trial_type": "action",
        "expected_label": str(expected_label),
        "transitions": transitions,
        "matched_expected_label": bool(matched),
        "operator_confirmed": bool(operator_confirmed),
        "success": bool(matched and operator_confirmed),
    }


def _run_continue_hold_trial(
    *,
    controller: EventOnsetController,
    device,
    hold_sec: float,
) -> dict:
    input(f"[LIVE] CONTINUE hold: stay relaxed/continue for {hold_sec:.1f}s. Press Enter to start.")
    start = time.monotonic()
    false_triggers = 0
    transitions: list[dict] = []
    while (time.monotonic() - start) < float(hold_sec):
        frames = device.read_frames()
        if not frames:
            time.sleep(0.01)
            continue
        for parsed in frames:
            rows = _rows_from_frame(parsed)
            for step in controller.ingest_rows(rows):
                if not step.decision.changed:
                    continue
                false_triggers += 1
                transitions.append(
                    {
                        "elapsed_sec": round(float(time.monotonic() - start), 3),
                        "emitted_class_name": str(step.decision.emitted_class_name),
                        "confidence": round(float(step.confidence), 4),
                        "energy": round(float(step.energy), 4),
                    }
                )
    no_unintended_motion = True if hasattr(controller.actuator, "get_info") and controller.actuator.get_info().get("type") == "StandaloneActuator" else _prompt_yes_no(
        "[LIVE] Was there no unintended prosthesis motion during the hold? [y/N]: "
    )
    success = bool(false_triggers <= 1 and no_unintended_motion)
    return {
        "trial_type": "continue_hold",
        "hold_sec": float(hold_sec),
        "false_triggers": int(false_triggers),
        "transitions": transitions,
        "operator_confirmed_no_unintended_motion": bool(no_unintended_motion),
        "success": bool(success),
    }


def _summarize_live_smoke(*, action_trials: list[dict], continue_hold: dict, action_trials_per_label: int) -> dict:
    per_label: dict[str, dict] = {}
    for record in action_trials:
        label = str(record["expected_label"])
        bucket = per_label.setdefault(label, {"total": 0, "successes": 0})
        bucket["total"] += 1
        bucket["successes"] += 1 if bool(record["success"]) else 0
    for label, bucket in per_label.items():
        bucket["pass"] = bool(bucket["successes"] >= 4 and bucket["total"] == action_trials_per_label)
    continue_summary = {
        "false_triggers": int(continue_hold["false_triggers"]),
        "operator_confirmed_no_unintended_motion": bool(
            continue_hold["operator_confirmed_no_unintended_motion"]
        ),
        "pass": bool(continue_hold["success"]),
    }
    return {
        "thresholds": {"min_action_successes": 4, "continue_false_triggers_max": 1},
        "per_label": per_label,
        "continue_hold": continue_summary,
        "trials": action_trials + [continue_hold],
        "passed": bool(all(bucket["pass"] for bucket in per_label.values()) and continue_summary["pass"]),
    }


def _run_live_smoke(
    *,
    args: argparse.Namespace,
    checkpoint: Path,
    model_path: Path,
    model_metadata: Path,
) -> dict:
    controller, device, actuator, _class_names, label_to_state = _build_live_components(
        args=args,
        checkpoint=checkpoint,
        model_path=model_path,
        model_metadata=model_metadata,
    )
    del label_to_state
    action_sequence = ["THUMB_UP", "TENSE_OPEN", "WRIST_CW"] * int(args.action_trials)
    action_trials: list[dict] = []
    try:
        for index, label in enumerate(action_sequence, start=1):
            action_trials.append(
                _run_action_trial(
                    controller=controller,
                    device=device,
                    expected_label=label,
                    trial_timeout_sec=float(args.trial_timeout_sec),
                    trial_index=index,
                )
            )
        continue_hold = _run_continue_hold_trial(
            controller=controller,
            device=device,
            hold_sec=float(args.continue_hold_sec),
        )
    finally:
        try:
            device.disconnect()
        finally:
            if hasattr(actuator, "disconnect"):
                actuator.disconnect()
    return _summarize_live_smoke(
        action_trials=action_trials,
        continue_hold=continue_hold,
        action_trials_per_label=int(args.action_trials),
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("event_release_validation")
    args = build_parser().parse_args()

    run_id, run_dir = ensure_run_dir(args.run_root, args.run_id, default_tag="event_release_validation")
    copy_config_snapshot(args.training_config, run_dir / "config_snapshots" / Path(args.training_config).name)
    copy_config_snapshot(args.runtime_config, run_dir / "config_snapshots" / Path(args.runtime_config).name)
    copy_config_snapshot(args.conversion_config, run_dir / "config_snapshots" / Path(args.conversion_config).name)

    checkpoint = _candidate_checkpoint(args)
    model_path = run_dir / "models" / "event_onset.mindir"
    model_metadata = run_dir / "models" / "event_onset.model_metadata.json"
    ckpt_eval_path = run_dir / "evaluation" / "control_eval_ckpt_summary.json"
    lite_eval_path = run_dir / "evaluation" / "control_eval_lite_summary.json"
    live_smoke_path = run_dir / "evaluation" / "live_smoke_summary.json"

    convert_cmd = [
        sys.executable,
        "scripts/convert_event_onset.py",
        "--config",
        str(args.conversion_config),
        "--training_config",
        str(args.training_config),
        "--checkpoint",
        str(checkpoint),
        "--output",
        str(model_path),
        "--metadata_output",
        str(model_metadata),
        "--device_target",
        str(args.convert_device_target),
        "--run_root",
        str(args.run_root),
        "--run_id",
        str(run_id),
    ]
    _run_checked("convert", convert_cmd)
    _run_checked(
        "control_eval_ckpt",
        _build_eval_cmd(
            args=args,
            output_json=ckpt_eval_path,
            backend="ckpt",
            checkpoint=checkpoint,
        ),
    )
    _run_checked(
        "control_eval_lite",
        _build_eval_cmd(
            args=args,
            output_json=lite_eval_path,
            backend="lite",
            checkpoint=checkpoint,
            model_path=model_path,
            model_metadata=model_metadata,
        ),
    )

    ckpt_summary = json.loads(ckpt_eval_path.read_text(encoding="utf-8"))
    lite_summary = json.loads(lite_eval_path.read_text(encoding="utf-8"))
    parity = _build_parity_summary(ckpt_summary=ckpt_summary, lite_summary=lite_summary)

    live_smoke = None
    if args.skip_live_smoke:
        live_smoke = {
            "status": "skipped",
            "reason": "skip_live_smoke=true",
            "passed": False,
        }
    else:
        live_smoke = _run_live_smoke(
            args=args,
            checkpoint=checkpoint,
            model_path=model_path,
            model_metadata=model_metadata,
        )
    dump_json(live_smoke_path, live_smoke)

    target_keys = _parse_target_keys(args.target_db5_keys)
    runtime_cfg = load_event_runtime_config(args.runtime_config)
    runtime_cfg.data.target_db5_keys = list(target_keys)
    label_spec = get_label_mode_spec(runtime_cfg.data.label_mode, runtime_cfg.data.target_db5_keys)
    _, mapping_by_name = load_and_validate_actuation_map(
        runtime_cfg.actuation_mapping_path,
        class_names=label_spec.class_names,
    )

    output_json = (
        Path(str(args.output_json)).resolve()
        if str(args.output_json or "").strip()
        else (run_dir / "release_validation_summary.json")
    )
    summary = {
        "status": "ok" if parity["passed"] and bool(live_smoke.get("passed", False)) else "needs_attention",
        "run_id": str(run_id),
        "candidate_run_id": str(args.candidate_run_id),
        "checkpoint": str(checkpoint),
        "converted_model_path": str(model_path),
        "converted_model_metadata": str(model_metadata),
        "training_config": str(Path(args.training_config).resolve()),
        "runtime_config": str(Path(args.runtime_config).resolve()),
        "target_db5_keys": list(target_keys),
        "mapping": public_event_mapping(mapping_by_name),
        "ckpt_control_eval": ckpt_summary,
        "lite_control_eval": lite_summary,
        "parity": parity,
        "live_smoke": live_smoke,
        "release_contract": {
            "CONTINUE": "keep current state",
            "TENSE_OPEN": "explicit open/release",
            "THUMB_UP": "latched action",
            "WRIST_CW": "latched action",
            "release_mode": str(runtime_cfg.runtime.release_mode),
        },
    }
    dump_json(output_json, summary)
    logger.info("release_validation_summary=%s", output_json)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
