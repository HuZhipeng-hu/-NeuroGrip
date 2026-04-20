# NeuroGrip Demo3

NeuroGrip Demo3 is an event-driven prosthesis control pipeline based on 8-channel sEMG and 6-axis IMU signals.

The complete technical chain in this package is:

1. collect wearer data
2. build the event-onset training set
3. finetune the two-stage event model
4. convert `CKPT -> MindIR + metadata`
5. evaluate the model with `ckpt` and `lite`
6. deploy the converted model to Kunpeng Pro
7. run the prosthesis control runtime

## Control Contract

- `CONTINUE`: keep the current prosthesis state
- `TENSE_OPEN`: switch to the open state and latch
- `V_SIGN`: switch to the `V_SIGN` state and latch
- `THUMB_UP`: switch to the `THUMB_UP` state and latch
- `WRIST_CW`: switch to the clockwise wrist state and latch

The runtime uses `release_mode=command_only`, so state changes are driven by explicit gesture commands.

## Included Assets

This package already includes the official baseline assets:

- `checkpoints/event_onset_best.ckpt`
- `models/event_onset.mindir`
- `models/event_onset.model_metadata.json`
- `artifacts/runs/vsign_mainline_clean_full_b0_s42_supp100/...`

It also includes the official dataset subset and the fixed split used by the baseline run:

- `../data/recordings_manifest.csv`
- `artifacts/splits/event_onset_demo3_split_manifest.json`

## Main Entrypoints

- collection: `scripts/collect_event_data.py`
- continuous collection: `scripts/collect_event_data_continuous.py`
- finetune: `scripts/finetune_event_onset.py`
- convert: `scripts/convert_event_onset.py`
- control evaluation: `scripts/evaluate_event_demo_control.py`
- runtime: `scripts/run_event_runtime.py`
- deployment: `scripts/deploy_event_release_bundle.py`
- environment check: `scripts/preflight.py`
- unsupervised pretrain: `python unsupervised/train_autoencoder.py --config configs/unsupervised_event_onset.yaml`

## Unsupervised Mode

We added an autoencoder-based self-supervised path to learn embeddings without gesture labels. It reuses the event-onset data loader and evaluates embeddings with K-Means/ARI/NMI/Silhouette. Configure via `configs/unsupervised_event_onset.yaml` and run `python unsupervised/train_autoencoder.py` (MindSpore required). Outputs (checkpoint, embeddings, metrics) are saved under `artifacts/runs/<run_id>/`.

## Reproduce The Baseline

Use:

- `docs/reproduction_runbook.md`

This runbook covers:

- environment check
- finetune
- convert
- `ckpt` evaluation
- `lite` evaluation
- expected output files

## Deploy On Kunpeng Pro

Use:

- `docs/deployment_runbook.md`

This runbook covers:

- dependency installation
- model file placement
- runtime configuration
- Kunpeng Pro startup
- live runtime execution

The included `configs/runtime_event_onset_kunpeng_pro.yaml` is the verified Kunpeng Pro runtime configuration used for the final hardware smoke.

## Baseline Metrics

The official baseline in this package is:

- run id: `vsign_mainline_clean_full_b0_s42_supp100`
- `test_accuracy = 0.8342`
- ``ckpt/lite` parity: passed

Detailed metrics and logs are stored under:

- `docs/baseline_summary.json`
- `artifacts/runs/vsign_mainline_clean_full_b0_s42_supp100/`

The package also includes the latest Kunpeng Pro live runtime verification logs under:

- `artifacts/runtime_sessions/20260321_220737_event_runtime/`
