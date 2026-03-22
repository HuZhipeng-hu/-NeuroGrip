"""Export the minimal cloud-side training/conversion bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from scripts.bundle_utils import CODE_ROOT, sha256_file, write_repo_bundle

CLOUD_BUNDLE_ENTRIES = [
    "event_onset",
    "shared",
    "training",
    "scripts/bundle_utils.py",
    "scripts/build_event_release_bundle.py",
    "scripts/audit_event_vsign_candidate.py",
    "scripts/compare_event_candidates.py",
    "scripts/collection_utils.py",
    "scripts/convert_event_onset.py",
    "scripts/evaluate_event_demo_control.py",
    "scripts/finetune_event_onset.py",
    "scripts/run_event_cloud_release.py",
    "scripts/run_event_runtime.py",
    "scripts/tune_event_runtime_thresholds.py",
    "scripts/validate_event_release.py",
    "scripts/verify_event_runtime_replay.py",
    "configs/conversion_event_onset.yaml",
    "configs/event_actuation_mapping.yaml",
    "configs/runtime_event_onset.yaml",
    "configs/training_event_onset.yaml",
    "configs/training_event_onset_vsign_focus.yaml",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the cloud-side event release bundle.")
    parser.add_argument("--output", default="artifacts/bundles/event_cloud_bundle.zip")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bundle_path = write_repo_bundle(output_zip=args.output, entries=CLOUD_BUNDLE_ENTRIES)
    summary = {
        "bundle_type": "cloud_training_release",
        "bundle_path": str(bundle_path.resolve()),
        "bundle_sha256": sha256_file(bundle_path),
        "entry_count": len(CLOUD_BUNDLE_ENTRIES),
        "repo_root": str(CODE_ROOT),
    }
    summary_path = bundle_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
