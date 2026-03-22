# Reproduction Runbook

This runbook reproduces the official NeuroGrip Demo3 baseline from the included dataset subset and fixed split.

## 1. Environment Check

```bash
python scripts/preflight.py --mode ascend --wearer_data_dir ../data
```

For a local machine without Ascend training support:

```bash
python scripts/preflight.py --mode local --wearer_data_dir ../data
```

## 2. Finetune

```bash
python scripts/finetune_event_onset.py \
  --config configs/training_event_onset.yaml \
  --data_dir ../data \
  --recordings_manifest ../data/recordings_manifest.csv \
  --split_manifest_in artifacts/splits/event_onset_demo3_split_manifest.json \
  --run_root artifacts/runs \
  --run_id submission_candidate
```

## 3. Convert

```bash
python scripts/convert_event_onset.py \
  --config configs/conversion_event_onset.yaml \
  --training_config configs/training_event_onset.yaml \
  --checkpoint artifacts/runs/submission_candidate/checkpoints/event_onset_best.ckpt \
  --output artifacts/runs/submission_candidate/models/event_onset.mindir \
  --metadata_output artifacts/runs/submission_candidate/models/event_onset.model_metadata.json \
  --run_root artifacts/runs \
  --run_id submission_candidate
```

## 4. Evaluate With `ckpt`

```bash
python scripts/evaluate_event_demo_control.py \
  --run_root artifacts/runs \
  --run_id submission_candidate \
  --training_config configs/training_event_onset.yaml \
  --runtime_config configs/runtime_event_onset.yaml \
  --data_dir ../data \
  --recordings_manifest ../data/recordings_manifest.csv \
  --split_manifest artifacts/splits/event_onset_demo3_split_manifest.json \
  --eval_split test \
  --backend ckpt \
  --device_target Ascend
```

## 5. Evaluate With `lite`

```bash
python scripts/evaluate_event_demo_control.py \
  --run_root artifacts/runs \
  --run_id submission_candidate \
  --training_config configs/training_event_onset.yaml \
  --runtime_config configs/runtime_event_onset.yaml \
  --data_dir ../data \
  --recordings_manifest ../data/recordings_manifest.csv \
  --split_manifest artifacts/splits/event_onset_demo3_split_manifest.json \
  --eval_split test \
  --backend lite \
  --device_target CPU \
  --model_path artifacts/runs/submission_candidate/models/event_onset.mindir \
  --model_metadata artifacts/runs/submission_candidate/models/event_onset.model_metadata.json
```

## 6. Included Baseline Artifacts

The package already contains the official baseline outputs:

- `checkpoints/event_onset_best.ckpt`
- `models/event_onset.mindir`
- `models/event_onset.model_metadata.json`
- `artifacts/runs/vsign_mainline_clean_full_b0_s42_supp100/offline_summary.json`
- `artifacts/runs/vsign_mainline_clean_full_b0_s42_supp100/evaluation/control_eval_ckpt_test_summary.json`
- `artifacts/runs/vsign_mainline_clean_full_b0_s42_supp100/evaluation/control_eval_lite_test_summary.json`

## Expected Outputs

A completed candidate run should provide:

- `artifacts/runs/<run_id>/offline_summary.json`
- `artifacts/runs/<run_id>/evaluation/control_eval_ckpt_test_summary.json`
- `artifacts/runs/<run_id>/evaluation/control_eval_lite_test_summary.json`
