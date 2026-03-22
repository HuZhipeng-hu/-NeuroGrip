"""Helpers for export/session/release zip bundles."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Iterable

CODE_ROOT = Path(__file__).resolve().parent.parent


def iter_repo_files(entries: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for raw in entries:
        path = (CODE_ROOT / raw).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Bundle entry not found: {path}")
        if path.is_file():
            files.append(path)
            continue
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            if "__pycache__" in child.parts:
                continue
            if child.suffix in {".pyc", ".pyo"}:
                continue
            files.append(child)
    return files


def write_repo_bundle(*, output_zip: str | Path, entries: Iterable[str]) -> Path:
    output_path = Path(output_zip)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in iter_repo_files(entries):
            archive.write(path, arcname=str(path.relative_to(CODE_ROOT)).replace("\\", "/"))
    return output_path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_text_into_zip(archive: zipfile.ZipFile, arcname: str, text: str) -> None:
    archive.writestr(str(arcname).replace("\\", "/"), text.encode("utf-8"))


def dump_json_into_zip(archive: zipfile.ZipFile, arcname: str, payload: dict) -> None:
    dump_text_into_zip(archive, arcname, json.dumps(payload, ensure_ascii=False, indent=2))


def dump_manifest_csv(archive: zipfile.ZipFile, arcname: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    dump_text_into_zip(archive, arcname, buffer.getvalue())
