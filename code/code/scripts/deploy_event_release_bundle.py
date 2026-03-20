"""Deploy a release bundle onto the runtime device workspace."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(CODE_ROOT))

from scripts.build_event_release_bundle import REQUIRED_DEPLOY_ENTRIES
from shared.run_utils import dump_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy a release bundle onto this workspace.")
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--repo_root", default=str(CODE_ROOT))
    parser.add_argument("--output_json", default=None)
    return parser


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _validate_bundle(archive: zipfile.ZipFile) -> list[str]:
    names = set(archive.namelist())
    missing = [arcname for arcname in REQUIRED_DEPLOY_ENTRIES if arcname not in names]
    if missing:
        raise ValueError(f"release bundle is missing required entries: {missing}")
    return sorted(names)


def deploy_release_bundle(*, bundle: str | Path, repo_root: str | Path) -> dict:
    bundle_path = Path(bundle).resolve()
    root = Path(repo_root).resolve()
    backup_dir = root / "deploy_backups" / _timestamp()
    backup_dir.mkdir(parents=True, exist_ok=True)

    deployed_files: list[str] = []
    backup_files: list[str] = []

    with zipfile.ZipFile(bundle_path, "r") as archive:
        names = _validate_bundle(archive)
        candidates = list(REQUIRED_DEPLOY_ENTRIES.keys())
        if "checkpoints/event_onset_best.ckpt" in names:
            candidates.append("checkpoints/event_onset_best.ckpt")
        if "file_hashes_sha256.json" in names:
            candidates.append("file_hashes_sha256.json")

        for arcname in candidates:
            destination = root / arcname
            if destination.exists():
                backup_target = backup_dir / arcname
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup_target)
                backup_files.append(str(backup_target))
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(arcname, "r") as source, open(destination, "wb") as handle:
                shutil.copyfileobj(source, handle)
            deployed_files.append(str(destination))

    summary = {
        "status": "ok",
        "bundle_path": str(bundle_path),
        "repo_root": str(root),
        "backup_dir": str(backup_dir),
        "backup_files": backup_files,
        "deployed_files": deployed_files,
    }
    return summary


def main() -> None:
    args = build_parser().parse_args()
    summary = deploy_release_bundle(bundle=args.bundle, repo_root=args.repo_root)
    output_path = (
        Path(args.output_json).resolve()
        if str(args.output_json or "").strip()
        else (Path(args.repo_root).resolve() / "deploy_backups" / "latest_deploy_summary.json")
    )
    dump_json(output_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
