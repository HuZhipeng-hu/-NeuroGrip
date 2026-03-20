from __future__ import annotations

import pytest

from scripts.calibrate_event_runtime import _build_compare_report, _choose_runtime_source


def test_choose_runtime_source_prefers_tuned_only_when_rank_improves() -> None:
    before = {
        "command_success_rate": 0.82,
        "false_trigger_rate": 0.12,
        "false_release_rate": 0.00,
    }
    after_better = {
        "command_success_rate": 0.88,
        "false_trigger_rate": 0.10,
        "false_release_rate": 0.00,
    }
    after_equal = {
        "command_success_rate": 0.82,
        "false_trigger_rate": 0.12,
        "false_release_rate": 0.00,
    }

    assert _choose_runtime_source(before=before, after=after_better) == "tuned"
    assert _choose_runtime_source(before=before, after=after_equal) == "default"


def test_build_compare_report_tracks_expected_deltas() -> None:
    before = {
        "command_success_rate": 0.70,
        "false_trigger_rate": 0.20,
        "false_release_rate": 0.05,
    }
    after = {
        "command_success_rate": 0.85,
        "false_trigger_rate": 0.10,
        "false_release_rate": 0.00,
    }
    report = _build_compare_report(
        before=before,
        after=after,
        selected_source="tuned",
        selected_runtime_config="runtime_event_onset_calibrated.yaml",
    )
    assert report["selected_source"] == "tuned"
    assert report["selected_runtime_config"].endswith("runtime_event_onset_calibrated.yaml")
    assert report["delta"]["command_success_rate"] == pytest.approx(0.15)
    assert report["delta"]["false_trigger_rate"] == pytest.approx(-0.1)
    assert report["delta"]["false_release_rate"] == pytest.approx(-0.05)
