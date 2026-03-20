# ModelArts Cloud Sync 2026-03-18

This folder preserves the key artifacts copied from the Huawei ModelArts run so the
project no longer depends on the remote instance to recover the release candidate.

## Synced Core Model Artifacts

- `checkpoints/event_onset_scr22_best.ckpt`
- `models/event_onset_scr22.mindir`
- `models/event_onset_scr22.model_metadata.json`
- `configs/runtime_event_onset_scr22_source.yaml`

## Synced Run Evidence

### `scr22_candidate/`

- `offline_summary.json`
- `test_metrics.json`
- `control_eval_summary.json`
- `control_eval_summary_lite.json`
- `run_metadata.json`
- `training_history.csv`

Key metrics:

- CKPT control eval:
  - `event_action_accuracy = 0.6875`
  - `command_success_rate = 0.9411764705882353`
  - `false_trigger_rate = 0.058823529411764705`
  - `false_release_rate = 0.0`
- Lite control eval:
  - same as CKPT

### `baseline_tuning/`

- `offline_summary.json`
- `control_eval_summary_tuned_ckpt.json`
- `runtime_threshold_tuning_summary.json`
- `runtime_threshold_tuning_summary.csv`
- `runtime_event_onset_demo3_latch_tuned.yaml`

Key metrics:

- Tuned baseline control eval:
  - `event_action_accuracy = 0.8125`
  - `command_success_rate = 0.8823529411764706`
  - `false_trigger_rate = 0.11764705882352941`
  - `false_release_rate = 0.0`

### Root-Level Log

- `s3_demo3_0317_scr_tuned_screen.log`

## Recommendation

Keep these artifacts locally as the authoritative recovery copy.
Do not push the checkpoint, MindIR, or large logs to the default GitHub branch unless a
separate release-assets or LFS strategy is explicitly chosen.
