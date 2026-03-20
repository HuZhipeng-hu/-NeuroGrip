from __future__ import annotations

import pytest

from scripts.validate_event_release import _build_parity_summary, _summarize_live_smoke


def test_build_parity_summary_applies_release_thresholds() -> None:
    ckpt = {
        "command_success_rate": 0.90,
        "false_trigger_rate": 0.10,
        "false_release_rate": 0.00,
        "event_action_accuracy": 0.84,
    }
    lite = {
        "command_success_rate": 0.87,
        "false_trigger_rate": 0.12,
        "false_release_rate": 0.01,
        "event_action_accuracy": 0.83,
    }
    summary = _build_parity_summary(ckpt_summary=ckpt, lite_summary=lite)
    assert summary["passed"] is True
    assert summary["deltas"]["command_success_rate"] == pytest.approx(0.03)
    assert summary["deltas"]["false_trigger_rate"] == pytest.approx(0.02)


def test_summarize_live_smoke_requires_four_successes_and_clean_continue() -> None:
    action_trials = [
        {"expected_label": "THUMB_UP", "success": True},
        {"expected_label": "THUMB_UP", "success": True},
        {"expected_label": "THUMB_UP", "success": True},
        {"expected_label": "THUMB_UP", "success": True},
        {"expected_label": "THUMB_UP", "success": False},
        {"expected_label": "WRIST_CW", "success": True},
        {"expected_label": "WRIST_CW", "success": True},
        {"expected_label": "WRIST_CW", "success": True},
        {"expected_label": "WRIST_CW", "success": True},
        {"expected_label": "WRIST_CW", "success": False},
        {"expected_label": "TENSE_OPEN", "success": True},
        {"expected_label": "TENSE_OPEN", "success": True},
        {"expected_label": "TENSE_OPEN", "success": True},
        {"expected_label": "TENSE_OPEN", "success": True},
        {"expected_label": "TENSE_OPEN", "success": False},
    ]
    continue_hold = {
        "trial_type": "continue_hold",
        "false_triggers": 1,
        "operator_confirmed_no_unintended_motion": True,
        "success": True,
    }
    summary = _summarize_live_smoke(
        action_trials=action_trials,
        continue_hold=continue_hold,
        action_trials_per_label=5,
    )
    assert summary["per_label"]["THUMB_UP"]["pass"] is True
    assert summary["per_label"]["WRIST_CW"]["pass"] is True
    assert summary["per_label"]["TENSE_OPEN"]["pass"] is True
    assert summary["continue_hold"]["pass"] is True
    assert summary["passed"] is True
