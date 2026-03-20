"""Build a deployable release bundle from converted event-onset artifacts."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(CODE_ROOT))

from scripts.bundle_utils import dump_json_into_zip, sha256_file
from shared.run_utils import dump_json


REQUIRED_DEPLOY_ENTRIES = {
    "models/event_onset.mindir": "MindIR model",
    "models/event_onset.model_metadata.json": "model metadata",
    "configs/runtime_event_onset.yaml": "runtime config",
    "configs/event_actuation_mapping.yaml": "actuation mapping",
    "release_summary.json": "release summary",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a deployable event release bundle.")
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--output", default="artifacts/bundles/event_release_bundle.zip")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--model_metadata", required=True)
    parser.add_argument("--runtime_config", default="configs/runtime_event_onset.yaml")
    parser.add_argument("--actuation_mapping", default="configs/event_actuation_mapping.yaml")
    parser.add_argument("--release_summary", required=True)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--include_checkpoint", action="store_true")
    parser.add_argument("--output_json", default=None)
    return parser


def _ensure_file(path: str | Path, desc: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"{desc} not found: {resolved}")
    return resolved


def build_release_bundle(
    *,
    output: str | Path,
    model_path: str | Path,
    model_metadata: str | Path,
    runtime_config: str | Path,
    actuation_mapping: str | Path,
    release_summary: str | Path,
    checkpoint: str | Path | None = None,
    include_checkpoint: bool = False,
    run_id: str | None = None,
) -> tuple[Path, dict]:
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolved = {
        "models/event_onset.mindir": _ensure_file(model_path, "MindIR model"),
        "models/event_onset.model_metadata.json": _ensure_file(model_metadata, "model metadata"),
        "configs/runtime_event_onset.yaml": _ensure_file(runtime_config, "runtime config"),
        "configs/event_actuation_mapping.yaml": _ensure_file(actuation_mapping, "actuation mapping"),
        "release_summary.json": _ensure_file(release_summary, "release summary"),
    }
    if include_checkpoint:
        if not checkpoint:
            raise ValueError("include_checkpoint=true requires --checkpoint")
        resolved["checkpoints/event_onset_best.ckpt"] = _ensure_file(checkpoint, "checkpoint")

    file_hashes: dict[str, str] = {}
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, source in resolved.items():
            archive.write(source, arcname=arcname)
            file_hashes[arcname] = sha256_file(source)
        dump_json_into_zip(archive, "file_hashes_sha256.json", file_hashes)

    summary = {
        "status": "ok",
        "bundle_type": "event_release_bundle",
        "run_id": str(run_id) if run_id else None,
        "bundle_path": str(output_path),
        "bundle_sha256": sha256_file(output_path),
        "included_checkpoint": bool(include_checkpoint),
        "files": sorted(resolved.keys()),
        "file_hashes": file_hashes,
    }
    return output_path, summary


def main() -> None:
    args = build_parser().parse_args()
    bundle_path, summary = build_release_bundle(
        output=args.output,
        model_path=args.model_path,
        model_metadata=args.model_metadata,
        runtime_config=args.runtime_config,
        actuation_mapping=args.actuation_mapping,
        release_summary=args.release_summary,
        checkpoint=args.checkpoint,
        include_checkpoint=bool(args.include_checkpoint),
        run_id=args.run_id,
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
