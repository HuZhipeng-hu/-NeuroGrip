"""Export the minimal Pi-side collection/deploy/runtime bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from scripts.bundle_utils import CODE_ROOT, sha256_file, write_repo_bundle

PI_BUNDLE_ENTRIES = [
    "event_onset",
    "runtime",
    "shared",
    "training",
    "scripts/build_event_release_bundle.py",
    "scripts/bundle_utils.py",
    "scripts/calibrate_event_runtime.py",
    "scripts/compare_event_candidates.py",
    "scripts/collect_event_data.py",
    "scripts/collect_event_data_continuous.py",
    "scripts/collection_utils.py",
    "scripts/deploy_event_release_bundle.py",
    "scripts/emg_armband.py",
    "scripts/package_event_session_bundle.py",
    "scripts/run_event_runtime.py",
    "scripts/tune_event_runtime_thresholds.py",
    "scripts/verify_event_runtime_replay.py",
    "configs/event_actuation_mapping.yaml",
    "configs/runtime_event_onset.yaml",
    "configs/runtime_event_onset_pi_live_tuned.yaml",
    "configs/runtime_event_onset_pi_live_stable.yaml",
    "configs/training_event_onset.yaml",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the Pi-side runtime/collection bundle.")
    parser.add_argument("--output", default="artifacts/bundles/event_pi_bundle.zip")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bundle_path = write_repo_bundle(output_zip=args.output, entries=PI_BUNDLE_ENTRIES)
    summary = {
        "bundle_type": "pi_collect_runtime_release",
        "bundle_path": str(bundle_path.resolve()),
        "bundle_sha256": sha256_file(bundle_path),
        "entry_count": len(PI_BUNDLE_ENTRIES),
        "repo_root": str(CODE_ROOT),
    }
    summary_path = bundle_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
