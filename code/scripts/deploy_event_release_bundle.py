"""Deploy a release bundle onto the runtime device workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(CODE_ROOT))

from scripts.build_event_release_bundle import REQUIRED_DEPLOY_ENTRIES
from scripts.bundle_utils import sha256_file
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


def _sha256_bytes(payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(payload)
    return digest.hexdigest()


def _load_bundle_hashes(archive: zipfile.ZipFile) -> dict[str, str]:
    if "file_hashes_sha256.json" not in archive.namelist():
        return {}
    payload = json.loads(archive.read("file_hashes_sha256.json").decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("file_hashes_sha256.json must contain an object")
    return {str(key): str(value) for key, value in payload.items()}


def _verify_archive_hashes(archive: zipfile.ZipFile, file_hashes: dict[str, str]) -> dict[str, str]:
    verified: dict[str, str] = {}
    for arcname, expected_hash in file_hashes.items():
        if arcname not in archive.namelist():
            raise ValueError(f"release bundle hash manifest references missing entry: {arcname}")
        actual_hash = _sha256_bytes(archive.read(arcname))
        if actual_hash != str(expected_hash):
            raise ValueError(
                f"release bundle hash mismatch for {arcname}: expected={expected_hash} actual={actual_hash}"
            )
        verified[str(arcname)] = str(actual_hash)
    return verified


def deploy_release_bundle(*, bundle: str | Path, repo_root: str | Path) -> dict:
    bundle_path = Path(bundle).resolve()
    root = Path(repo_root).resolve()
    backup_dir = root / "deploy_backups" / _timestamp()
    backup_dir.mkdir(parents=True, exist_ok=True)

    deployed_files: list[str] = []
    backup_files: list[str] = []

    with zipfile.ZipFile(bundle_path, "r") as archive:
        names = _validate_bundle(archive)
        bundle_hashes = _load_bundle_hashes(archive)
        archive_verified_hashes = _verify_archive_hashes(archive, bundle_hashes) if bundle_hashes else {}
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

    deployed_file_hashes = {
        str((root / arcname).resolve()): sha256_file(root / arcname)
        for arcname in REQUIRED_DEPLOY_ENTRIES.keys()
        if (root / arcname).exists()
    }
    if "checkpoints/event_onset_best.ckpt" in names and (root / "checkpoints" / "event_onset_best.ckpt").exists():
        deployed_file_hashes[str((root / "checkpoints" / "event_onset_best.ckpt").resolve())] = sha256_file(
            root / "checkpoints" / "event_onset_best.ckpt"
        )

    summary = {
        "status": "ok",
        "bundle_path": str(bundle_path),
        "bundle_sha256": sha256_file(bundle_path),
        "repo_root": str(root),
        "backup_dir": str(backup_dir),
        "backup_files": backup_files,
        "deployed_files": deployed_files,
        "archive_hashes_verified": bool(bundle_hashes),
        "archive_verified_hashes": archive_verified_hashes,
        "deployed_file_hashes": deployed_file_hashes,
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
