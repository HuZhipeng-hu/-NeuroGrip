# Model 90 Sprint Runbook

## Goal

This runbook is for the demo3 two-stage release candidate:

- `CONTINUE`
- `TENSE_OPEN`
- `THUMB_UP`
- `WRIST_CW`

Recommended semantics:

- `CONTINUE`: no new command, keep the current prosthesis state
- `TENSE_OPEN`: switch to the fully open pose and latch
- `THUMB_UP` and `WRIST_CW`: switch to target state and latch
- `WRIST_CCW`, `V_SIGN`, and `OK_SIGN` remain extension classes outside the default demo3 path

This is an event-driven latch protocol. It is not continuous motion mirroring.

Main entry:

- `scripts/train_event_model_90_sprint.py`

Default workflow:

1. collection audit
2. filtered demo3 manifest build
3. deterministic grouped-file split build
4. bounded screen
5. longrun stability check
6. neighbor verification
7. audit

## Standard Manual Deployment Flow

The sprint pipeline is for bounded research and offline candidate selection.
Routine deployment should use the fixed manual split:

1. Orange Pi collects a new wearer session
2. Orange Pi packages that session into a session bundle
3. The session bundle is uploaded to Huawei Cloud
4. Huawei Cloud runs one fixed `finetune -> convert -> parity -> release bundle` flow
5. The release bundle is downloaded back to Orange Pi
6. Orange Pi deploys the release bundle and starts `lite` runtime

Bundle export helpers:

```bash
python scripts/export_event_cloud_bundle.py --output artifacts/bundles/event_cloud_bundle.zip
python scripts/export_event_pi_bundle.py --output artifacts/bundles/event_pi_bundle.zip
```

Package one Pi session:

```bash
python scripts/package_event_session_bundle.py \
  --data_dir ../data \
  --recordings_manifest recordings_manifest.csv \
  --session_id s1 \
  --output artifacts/bundles/session_s1.zip
```

Run the fixed cloud release flow:

```bash
python scripts/run_event_cloud_release.py \
  --session_bundle artifacts/bundles/session_s1.zip \
  --run_root artifacts/runs \
  --run_id release_s1 \
  --device_target Ascend \
  --convert_device_target Ascend \
  --eval_device_target CPU \
  --target_db5_keys TENSE_OPEN,THUMB_UP,WRIST_CW
```

Deploy the release bundle on the Pi:

```bash
python scripts/deploy_event_release_bundle.py \
  --bundle artifacts/bundles/release_s1_release_bundle.zip
```

Current artifact roles must stay separate:

- preferred deploy baseline: `scr22`
- manual cloud release-flow validation sample: `smoke_release_s3_bg`

Reference notes:

- `docs/cloud_release_v1_notes.md`
- `docs/pi_recovery_runbook.md`

## One-Command Flow

After collecting new data:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage all \
  --device_target Ascend \
  --device_id 0 \
  --data_dir ../data \
  --recordings_manifest recordings_manifest.csv \
  --run_prefix s2_model90
```

Main outputs:

- `artifacts/runs/s2_model90_prepare_summary.json`
- `artifacts/runs/s2_model90_baseline_summary.json`
- `artifacts/runs/s2_model90_screen_summary.json`
- `artifacts/runs/s2_model90_longrun_summary.json`
- `artifacts/runs/s2_model90_neighbor_summary.json`
- `artifacts/runs/s2_model90_tune_summary.json`
- `artifacts/runs/s2_model90_audit_report.json`
- `artifacts/runs/s2_model90_pipeline_report.json`

## Prepare Only

Use this before long device runs:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage prepare \
  --device_target CPU \
  --data_dir ../data \
  --recordings_manifest recordings_manifest.csv \
  --run_prefix s2_model90
```

Default prepare rules:

- only `event_onset` capture mode is kept
- dead-channel clips are dropped
- action clips require at least `2` selected windows
- `CONTINUE` clips require at least `1` selected window
- `CONTINUE` clips may keep `retake_recommended` quality if no dead channel is present

Useful optional flags:

- `--prepare_session_id s2`
- `--prepare_target_per_class 12`
- `--prepare_relax_target_count 24`
- `--prepare_action_min_selected_windows 2`
- `--prepare_relax_min_selected_windows 1`
- `--prepare_relax_allow_retake_quality true`
- `--prepare_output_manifest ../data/s2_model90_demo3_train_manifest.csv`

The `prepare_relax_*` flag names are kept for backward compatibility. They control the public `CONTINUE` background class.

## Stage Commands

Baseline:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage baseline \
  --device_target Ascend \
  --device_id 0 \
  --run_prefix s2_model90
```

Screen:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage screen \
  --device_target Ascend \
  --device_id 0 \
  --run_prefix s2_model90 \
  --screen_split_seed 42 \
  --screen_loss_types cross_entropy,cb_focal \
  --screen_base_channels 16,24 \
  --screen_freeze_emg_epochs 6,8,10 \
  --screen_encoder_lr_ratios 0.24,0.3,0.36
```

Longrun:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage longrun \
  --device_target Ascend \
  --device_id 0 \
  --run_prefix s2_model90 \
  --longrun_seeds 42,52,62
```

Neighbor verification:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage neighbor \
  --device_target Ascend \
  --device_id 0 \
  --run_prefix s2_model90
```

Neighbor only checks five variants around the best longrun candidate:

- `ref`
- `lr_down`
- `lr_up`
- `freeze_down`
- `freeze_up`

Runtime threshold tuning:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage tune \
  --device_target Ascend \
  --device_id 0 \
  --run_prefix s2_model90
```

The current release default runtime thresholds are already baked into `configs/runtime_event_onset.yaml`.
Only keep a new tuned configuration if it beats the current release baseline on online control metrics.

Pipeline audit:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage audit \
  --device_target Ascend \
  --device_id 0 \
  --run_prefix s2_model90
```

## Audit Reading Guide

Primary file:

- `artifacts/runs/<run_prefix>_audit_report.json`

Root cause categories:

- `artifact_contract_bug`
- `implementation_bug`
- `hyperparameter_underfit`
- `data_bottleneck`

Release-candidate interpretation:

- `design`, `implementation`, and `stability` must pass
- `param_coverage` should pass, or remain as the only clearly documented blocker
- if `neighbor` shows no significant improvement and the first three gates pass, the next likely bottlenecks are data quality, sampling consistency, and task difficulty rather than hidden implementation bugs

Key fields:

- `root_cause_category`
- `root_cause_summary`
- `blocking_issues`
- `goal_assessment`

## Remote Execution

ModelArts Ascend is the preferred training target for this release-candidate line. Use separate runs for independent experiments; do not treat this sprint script as distributed training.

## Acceptance Targets

Primary offline gate:

- `event_action_accuracy >= 0.90`

Secondary offline gate:

- `event_action_macro_f1 >= 0.88`

Runtime gate:

- `command_success_rate >= 0.90`
- `false_trigger_rate <= 0.05`
- `false_release_rate <= 0.05`

Deployment parity gate:

- `CKPT` vs `MindIR/Lite` `command_success_rate` delta `<= 0.05`
- `false_trigger_rate` delta `<= 0.05`
- `false_release_rate` delta `<= 0.02`
- `event_action_accuracy` delta `<= 0.02`

## Post-Freeze Short Calibration

Frozen demo3 releases may still run a per-wear short calibration pass. This does not retrain the model and does not change weights.

```bash
python scripts/calibrate_event_runtime.py \
  --candidate_run_id s3_demo3_release \
  --runtime_config configs/runtime_event_onset.yaml \
  --backend lite \
  --device_target CPU \
  --port COM5
```

The calibration protocol is fixed:

- `CONTINUE`: 5 short static clips
- `TENSE_OPEN`: 1 short continuous onset run
- `THUMB_UP`: 1 short continuous onset run
- `WRIST_CW`: 1 short continuous onset run

Main outputs:

- `runtime_event_onset_calibrated.yaml`
- `calibration_summary.json`
- `calibration_compare_report.json`

## Post-Freeze Release Validation

The final release validation path is:

1. convert the selected checkpoint to `MindIR`
2. run `ckpt` control evaluation
3. run `lite` control evaluation
4. run the real prosthesis smoke test

```bash
python scripts/validate_event_release.py \
  --candidate_run_id s3_demo3_release \
  --runtime_config configs/runtime_event_onset.yaml \
  --convert_device_target Ascend \
  --eval_device_target CPU \
  --port COM5
```

The live smoke test is fixed:

- `THUMB_UP`: 5 trials, at least 4 successes
- `WRIST_CW`: 5 trials, at least 4 successes
- `TENSE_OPEN`: 5 trials, at least 4 successes
- `CONTINUE`: 10-second hold, at most 1 false trigger
