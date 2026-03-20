"""Run the standard cloud-side training + convert + release packaging flow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from scripts.build_event_release_bundle import build_release_bundle
from shared.run_utils import copy_config_snapshot, dump_json, ensure_run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run cloud-side training, conversion, parity, and release packaging.")
    parser.add_argument("--session_bundle", required=True)
    parser.add_argument("--run_root", default="artifacts/runs")
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--training_config", default="configs/training_event_onset.yaml")
    parser.add_argument("--conversion_config", default="configs/conversion_event_onset.yaml")
    parser.add_argument("--runtime_config", default="configs/runtime_event_onset.yaml")
    parser.add_argument("--actuation_mapping", default="configs/event_actuation_mapping.yaml")
    parser.add_argument("--data_dir_name", default="session_input/data")
    parser.add_argument("--device_target", default="Ascend", choices=["CPU", "GPU", "Ascend"])
    parser.add_argument("--convert_device_target", default="Ascend", choices=["CPU", "GPU", "Ascend"])
    parser.add_argument("--eval_device_target", default="CPU", choices=["CPU", "GPU", "Ascend"])
    parser.add_argument("--target_db5_keys", default="TENSE_OPEN,THUMB_UP,WRIST_CW")
    parser.add_argument("--budget_per_class", type=int, default=60)
    parser.add_argument("--budget_seed", type=int, default=42)
    parser.add_argument("--include_checkpoint", action="store_true")
    parser.add_argument("--output_bundle", default=None)
    parser.add_argument("--output_json", default=None)
    return parser


def _format_cmd(parts: list[str]) -> str:
    rendered: list[str] = []
    for part in parts:
        text = str(part)
        rendered.append(f'"{text}"' if " " in text else text)
    return " ".join(rendered)


def _run_checked(stage: str, cmd: list[str]) -> None:
    print(f"[CLOUD-RELEASE] {stage} -> {_format_cmd(cmd)}", flush=True)
    completed = subprocess.run(cmd, cwd=str(CODE_ROOT), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{stage} failed with rc={completed.returncode}")


def _safe_extract(zip_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            target = (output_dir / member.filename).resolve()
            if output_dir.resolve() not in target.parents and target != output_dir.resolve():
                raise ValueError(f"Unsafe zip entry detected: {member.filename}")
        archive.extractall(output_dir)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def run_cloud_release(
    *,
    session_bundle: str | Path,
    run_root: str | Path,
    run_id: str | None,
    training_config: str,
    conversion_config: str,
    runtime_config: str,
    actuation_mapping: str,
    data_dir_name: str,
    device_target: str,
    convert_device_target: str,
    eval_device_target: str,
    target_db5_keys: str,
    budget_per_class: int,
    budget_seed: int,
    include_checkpoint: bool,
    output_bundle: str | Path | None,
) -> tuple[Path, dict]:
    run_id_resolved, run_dir = ensure_run_dir(run_root, run_id, default_tag="event_cloud_release")
    copy_config_snapshot(training_config, run_dir / "config_snapshots" / Path(training_config).name)
    copy_config_snapshot(conversion_config, run_dir / "config_snapshots" / Path(conversion_config).name)
    copy_config_snapshot(runtime_config, run_dir / "config_snapshots" / Path(runtime_config).name)
    copy_config_snapshot(actuation_mapping, run_dir / "config_snapshots" / Path(actuation_mapping).name)

    session_bundle_path = Path(session_bundle).resolve()
    session_input_dir = run_dir / "session_input"
    _safe_extract(session_bundle_path, session_input_dir)
    manifest_path = session_input_dir / "recordings_manifest.csv"
    data_dir = run_dir / str(data_dir_name)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Session bundle missing recordings_manifest.csv: {session_bundle_path}")
    if not data_dir.exists():
        raise FileNotFoundError(f"Session bundle missing extracted data dir: {data_dir}")

    train_cmd = [
        sys.executable,
        "scripts/finetune_event_onset.py",
        "--config",
        str(training_config),
        "--data_dir",
        str(data_dir),
        "--recordings_manifest",
        str(manifest_path),
        "--device_target",
        str(device_target),
        "--run_root",
        str(run_root),
        "--run_id",
        str(run_id_resolved),
        "--target_db5_keys",
        str(target_db5_keys),
        "--budget_per_class",
        str(int(budget_per_class)),
        "--budget_seed",
        str(int(budget_seed)),
    ]
    _run_checked("finetune", train_cmd)

    checkpoint = run_dir / "checkpoints" / "event_onset_best.ckpt"
    model_path = run_dir / "models" / "event_onset.mindir"
    metadata_path = run_dir / "models" / "event_onset.model_metadata.json"
    convert_cmd = [
        sys.executable,
        "scripts/convert_event_onset.py",
        "--config",
        str(conversion_config),
        "--training_config",
        str(training_config),
        "--checkpoint",
        str(checkpoint),
        "--output",
        str(model_path),
        "--metadata_output",
        str(metadata_path),
        "--device_target",
        str(convert_device_target),
        "--run_root",
        str(run_root),
        "--run_id",
        str(run_id_resolved),
        "--target_db5_keys",
        str(target_db5_keys),
    ]
    _run_checked("convert", convert_cmd)

    ckpt_eval_path = run_dir / "evaluation" / "control_eval_ckpt_summary.json"
    lite_eval_path = run_dir / "evaluation" / "control_eval_lite_summary.json"
    for backend, output_json in (("ckpt", ckpt_eval_path), ("lite", lite_eval_path)):
        eval_cmd = [
            sys.executable,
            "scripts/evaluate_event_demo_control.py",
            "--run_root",
            str(run_root),
            "--run_id",
            str(run_id_resolved),
            "--training_config",
            str(training_config),
            "--runtime_config",
            str(runtime_config),
            "--data_dir",
            str(data_dir),
            "--recordings_manifest",
            str(manifest_path),
            "--target_db5_keys",
            str(target_db5_keys),
            "--backend",
            backend,
            "--device_target",
            str(eval_device_target),
            "--output_json",
            str(output_json),
        ]
        if backend == "ckpt":
            eval_cmd.extend(["--checkpoint", str(checkpoint)])
        else:
            eval_cmd.extend(["--model_path", str(model_path), "--model_metadata", str(metadata_path)])
        _run_checked(f"control_eval_{backend}", eval_cmd)

    session_metadata_path = session_input_dir / "session_metadata.json"
    session_metadata = _load_json(session_metadata_path) if session_metadata_path.exists() else {}
    ckpt_eval = _load_json(ckpt_eval_path)
    lite_eval = _load_json(lite_eval_path)
    parity = _build_parity_summary(ckpt_summary=ckpt_eval, lite_summary=lite_eval)
    release_summary = {
        "status": "ok" if parity["passed"] else "needs_attention",
        "run_id": str(run_id_resolved),
        "session_bundle": str(session_bundle_path),
        "session_metadata": session_metadata,
        "training_config": str(Path(training_config).resolve()),
        "conversion_config": str(Path(conversion_config).resolve()),
        "runtime_config": str(Path(runtime_config).resolve()),
        "actuation_mapping": str(Path(actuation_mapping).resolve()),
        "checkpoint_path": str(checkpoint.resolve()),
        "model_path": str(model_path.resolve()),
        "model_metadata_path": str(metadata_path.resolve()),
        "ckpt_control_eval": ckpt_eval,
        "lite_control_eval": lite_eval,
        "parity": parity,
    }
    release_summary_path = run_dir / "release" / "release_summary.json"
    dump_json(release_summary_path, release_summary)

    bundle_output = output_bundle or (Path(run_root).resolve() / "bundles" / f"{run_id_resolved}_release_bundle.zip")
    bundle_path, bundle_summary = build_release_bundle(
        output=bundle_output,
        model_path=model_path,
        model_metadata=metadata_path,
        runtime_config=runtime_config,
        actuation_mapping=actuation_mapping,
        release_summary=release_summary_path,
        checkpoint=checkpoint,
        include_checkpoint=bool(include_checkpoint),
        run_id=run_id_resolved,
    )
    summary = {
        "status": release_summary["status"],
        "run_id": str(run_id_resolved),
        "session_bundle": str(session_bundle_path),
        "release_summary_json": str(release_summary_path),
        "bundle": bundle_summary,
        "parity": parity,
    }
    return bundle_path, summary


def main() -> None:
    args = build_parser().parse_args()
    bundle_path, summary = run_cloud_release(
        session_bundle=args.session_bundle,
        run_root=args.run_root,
        run_id=args.run_id,
        training_config=args.training_config,
        conversion_config=args.conversion_config,
        runtime_config=args.runtime_config,
        actuation_mapping=args.actuation_mapping,
        data_dir_name=args.data_dir_name,
        device_target=args.device_target,
        convert_device_target=args.convert_device_target,
        eval_device_target=args.eval_device_target,
        target_db5_keys=args.target_db5_keys,
        budget_per_class=args.budget_per_class,
        budget_seed=args.budget_seed,
        include_checkpoint=bool(args.include_checkpoint),
        output_bundle=args.output_bundle,
    )
    output_path = (
        Path(args.output_json).resolve()
        if str(args.output_json or "").strip()
        else bundle_path.with_suffix(".cloud_release_summary.json")
    )
    dump_json(output_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
