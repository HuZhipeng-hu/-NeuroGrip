"""Package one wearer session into a portable training bundle."""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(CODE_ROOT))

from event_onset.manifest import EVENT_MANIFEST_FIELDS, load_event_manifest_rows
from scripts.bundle_utils import dump_json_into_zip, dump_manifest_csv, sha256_file
from shared.run_utils import dump_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package one wearer session into a zip bundle.")
    parser.add_argument("--data_dir", default="../data")
    parser.add_argument("--recordings_manifest", default="recordings_manifest.csv")
    parser.add_argument("--session_id", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--output_json", default=None)
    return parser


def _resolve_manifest(data_dir: Path, manifest_arg: str) -> Path:
    raw = Path(str(manifest_arg))
    if raw.is_absolute():
        return raw.resolve()
    return (data_dir / raw).resolve()


def _select_session_rows(*, data_dir: Path, manifest_path: Path, session_id: str) -> list[dict[str, str]]:
    entries = load_event_manifest_rows(manifest_path)
    rows = [
        row
        for row in entries.values()
        if str(row.get("session_id", "")).strip() == str(session_id).strip()
    ]
    if not rows:
        raise ValueError(f"No manifest rows found for session_id={session_id!r} in {manifest_path}")

    missing: list[str] = []
    for row in rows:
        candidate = (data_dir / str(row["relative_path"])).resolve()
        if not candidate.exists() or not candidate.is_file():
            missing.append(str(row["relative_path"]))
    if missing:
        raise FileNotFoundError(
            f"Session bundle packaging found missing files for session_id={session_id!r}: {missing}"
        )
    return sorted(rows, key=lambda current: str(current["relative_path"]))


def _build_session_metadata(*, rows: list[dict[str, str]], session_id: str) -> dict:
    labels = Counter(str(row.get("target_state", "")).strip().upper() for row in rows)
    devices = sorted({str(row.get("device_id", "")).strip() for row in rows if str(row.get("device_id", "")).strip()})
    wearing_states = sorted(
        {str(row.get("wearing_state", "")).strip() for row in rows if str(row.get("wearing_state", "")).strip()}
    )
    timestamps = sorted(str(row.get("timestamp", "")).strip() for row in rows if str(row.get("timestamp", "")).strip())
    return {
        "bundle_type": "event_session_bundle",
        "session_id": str(session_id),
        "recording_count": int(len(rows)),
        "labels": dict(sorted(labels.items())),
        "device_ids": devices,
        "wearing_states": wearing_states,
        "timestamp_range": {
            "start": timestamps[0] if timestamps else None,
            "end": timestamps[-1] if timestamps else None,
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_session_bundle(
    *,
    data_dir: str | Path,
    recordings_manifest: str | Path,
    session_id: str,
    output: str | Path,
) -> tuple[Path, dict]:
    data_root = Path(data_dir).resolve()
    manifest_path = _resolve_manifest(data_root, str(recordings_manifest))
    rows = _select_session_rows(data_dir=data_root, manifest_path=manifest_path, session_id=session_id)
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = _build_session_metadata(rows=rows, session_id=session_id)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        dump_json_into_zip(archive, "session_metadata.json", metadata)
        dump_manifest_csv(archive, "recordings_manifest.csv", EVENT_MANIFEST_FIELDS, rows)
        for row in rows:
            relative = str(row["relative_path"]).replace("\\", "/")
            absolute = (data_root / relative).resolve()
            archive.write(absolute, arcname=f"data/{relative}")

    summary = {
        "status": "ok",
        "bundle_type": "event_session_bundle",
        "session_id": str(session_id),
        "bundle_path": str(output_path),
        "bundle_sha256": sha256_file(output_path),
        "recording_count": int(len(rows)),
        "labels": metadata["labels"],
    }
    return output_path, summary


def main() -> None:
    args = build_parser().parse_args()
    output = args.output or f"artifacts/bundles/session_{args.session_id}.zip"
    bundle_path, summary = build_session_bundle(
        data_dir=args.data_dir,
        recordings_manifest=args.recordings_manifest,
        session_id=args.session_id,
        output=output,
    )
    summary_path = (
        Path(args.output_json).resolve()
        if str(args.output_json or "").strip()
        else bundle_path.with_suffix(".summary.json")
    )
    dump_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
