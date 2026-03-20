from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

from scripts.build_event_release_bundle import build_release_bundle
from scripts.deploy_event_release_bundle import deploy_release_bundle
from scripts.export_event_pi_bundle import PI_BUNDLE_ENTRIES
from scripts.package_event_session_bundle import build_session_bundle


def _write_csv(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "emg1",
                "emg2",
                "emg3",
                "emg4",
                "emg5",
                "emg6",
                "emg7",
                "emg8",
                "acc_x",
                "acc_y",
                "acc_z",
                "gyro_x",
                "gyro_y",
                "gyro_z",
                "angle_pitch",
                "angle_roll",
                "angle_yaw",
            ]
        )
        writer.writerows(rows)


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "relative_path",
        "gesture",
        "capture_mode",
        "start_state",
        "target_state",
        "user_id",
        "session_id",
        "device_id",
        "timestamp",
        "wearing_state",
        "recording_id",
        "sample_count",
        "clip_duration_ms",
        "pre_roll_ms",
        "device_sampling_rate_hz",
        "imu_sampling_rate_hz",
        "quality_status",
        "quality_reasons",
        "source_origin",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_build_session_bundle_filters_one_session(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    keep = data_dir / "THUMB_UP" / "keep.csv"
    other = data_dir / "WRIST_CW" / "other.csv"
    _write_csv(keep, [[0.0] * 17])
    _write_csv(other, [[1.0] * 17])
    manifest = data_dir / "recordings_manifest.csv"
    _write_manifest(
        manifest,
        [
            {
                "relative_path": "THUMB_UP/keep.csv",
                "gesture": "THUMB_UP",
                "capture_mode": "event_onset",
                "start_state": "CONTINUE",
                "target_state": "THUMB_UP",
                "user_id": "u1",
                "session_id": "s_keep",
                "device_id": "arm1",
                "timestamp": "20260318T200000",
                "wearing_state": "normal",
                "recording_id": "r1",
                "sample_count": "1",
                "clip_duration_ms": "3000",
                "pre_roll_ms": "400",
                "device_sampling_rate_hz": "500",
                "imu_sampling_rate_hz": "50",
                "quality_status": "pass",
                "quality_reasons": "",
                "source_origin": "test",
            },
            {
                "relative_path": "WRIST_CW/other.csv",
                "gesture": "WRIST_CW",
                "capture_mode": "event_onset",
                "start_state": "CONTINUE",
                "target_state": "WRIST_CW",
                "user_id": "u1",
                "session_id": "s_other",
                "device_id": "arm1",
                "timestamp": "20260318T200500",
                "wearing_state": "normal",
                "recording_id": "r2",
                "sample_count": "1",
                "clip_duration_ms": "3000",
                "pre_roll_ms": "400",
                "device_sampling_rate_hz": "500",
                "imu_sampling_rate_hz": "50",
                "quality_status": "pass",
                "quality_reasons": "",
                "source_origin": "test",
            },
        ],
    )

    bundle, summary = build_session_bundle(
        data_dir=data_dir,
        recordings_manifest=manifest,
        session_id="s_keep",
        output=tmp_path / "session_bundle.zip",
    )
    assert summary["recording_count"] == 1
    assert summary["labels"] == {"THUMB_UP": 1}
    with zipfile.ZipFile(bundle, "r") as archive:
        names = set(archive.namelist())
        assert "recordings_manifest.csv" in names
        assert "session_metadata.json" in names
        assert "data/THUMB_UP/keep.csv" in names
        assert "data/WRIST_CW/other.csv" not in names


def test_build_and_deploy_release_bundle_round_trip(tmp_path: Path) -> None:
    model = tmp_path / "build_src" / "event_onset.mindir"
    metadata = tmp_path / "build_src" / "event_onset.model_metadata.json"
    runtime_yaml = tmp_path / "build_src" / "runtime_event_onset.yaml"
    actuation_yaml = tmp_path / "build_src" / "event_actuation_mapping.yaml"
    summary_json = tmp_path / "build_src" / "release_summary.json"
    checkpoint = tmp_path / "build_src" / "event_onset_best.ckpt"
    for path, text in (
        (model, "mindir"),
        (metadata, '{"class_names":["CONTINUE","TENSE_OPEN","THUMB_UP","WRIST_CW"]}'),
        (runtime_yaml, "runtime: {}\n"),
        (actuation_yaml, "actuation_map: {}\n"),
        (summary_json, '{"status":"ok"}'),
        (checkpoint, "ckpt"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    bundle, summary = build_release_bundle(
        output=tmp_path / "event_release_bundle.zip",
        model_path=model,
        model_metadata=metadata,
        runtime_config=runtime_yaml,
        actuation_mapping=actuation_yaml,
        release_summary=summary_json,
        checkpoint=checkpoint,
        include_checkpoint=True,
        run_id="r1",
    )
    assert summary["included_checkpoint"] is True
    with zipfile.ZipFile(bundle, "r") as archive:
        names = set(archive.namelist())
        assert "models/event_onset.mindir" in names
        assert "configs/runtime_event_onset.yaml" in names
        assert "release_summary.json" in names
        assert "checkpoints/event_onset_best.ckpt" in names

    repo_root = tmp_path / "repo"
    old_runtime = repo_root / "configs" / "runtime_event_onset.yaml"
    old_runtime.parent.mkdir(parents=True, exist_ok=True)
    old_runtime.write_text("old-runtime", encoding="utf-8")

    deploy_summary = deploy_release_bundle(bundle=bundle, repo_root=repo_root)
    assert Path(deploy_summary["backup_dir"]).exists()
    assert (repo_root / "models" / "event_onset.mindir").read_text(encoding="utf-8") == "mindir"
    assert (repo_root / "configs" / "runtime_event_onset.yaml").read_text(encoding="utf-8") == "runtime: {}\n"
    assert any("runtime_event_onset.yaml" in item for item in deploy_summary["backup_files"])


def test_pi_bundle_entries_cover_runtime_imports() -> None:
    assert "training" in PI_BUNDLE_ENTRIES
    assert "scripts/build_event_release_bundle.py" in PI_BUNDLE_ENTRIES
    assert "configs/runtime_event_onset_pi_live_stable.yaml" in PI_BUNDLE_ENTRIES
