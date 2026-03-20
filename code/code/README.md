# NeuroGrip Demo3 Release Path

This repository exposes one recommended production path for the prosthesis demo:

- collect wearer data
- audit and prepare the demo3 training set
- finetune the event-onset model
- convert `CKPT -> MindIR + metadata`
- deploy the converted model to the runtime device
- run latched prosthesis control

The supported target is **event-driven latch control**, not continuous motion mirroring.

## Default Control Contract

- `CONTINUE`: no new command, keep the current prosthesis state
- `TENSE_OPEN`: switch to the fully open pose and latch
- `THUMB_UP`: switch to `THUMB_UP` and latch
- `WRIST_CW`: switch to the clockwise wrist pose and latch

Runtime default is `release_mode=command_only`, which means only explicit gesture switches change state.

## Main Entrypoints

- collect single clip: `scripts/collect_event_data.py`
- collect continuous stream: `scripts/collect_event_data_continuous.py`
- package one Pi session: `scripts/package_event_session_bundle.py`
- export cloud bundle: `scripts/export_event_cloud_bundle.py`
- export Pi bundle: `scripts/export_event_pi_bundle.py`
- bounded research flow: `scripts/train_event_model_90_sprint.py`
- direct finetune: `scripts/finetune_event_onset.py`
- convert: `scripts/convert_event_onset.py`
- cloud release flow: `scripts/run_event_cloud_release.py`
- deploy release bundle on Pi: `scripts/deploy_event_release_bundle.py`
- runtime: `scripts/run_event_runtime.py`
- control eval: `scripts/evaluate_event_demo_control.py`
- release validation: `scripts/validate_event_release.py`

## Collection

Single clip:

```bash
python scripts/collect_event_data.py \
  --data_dir ../data \
  --recordings_manifest recordings_manifest.csv \
  --target_state THUMB_UP \
  --start_state CONTINUE \
  --user_id demo_user \
  --session_id s1 \
  --device_id armband01 \
  --wearing_state normal \
  --duration_sec 3 \
  --port COM5 \
  --baudrate 115200
```

Continuous capture + auto-slice:

```bash
python scripts/collect_event_data_continuous.py \
  --config configs/training_event_onset.yaml \
  --data_dir ../data \
  --recordings_manifest recordings_manifest.csv \
  --target_state THUMB_UP \
  --start_state CONTINUE \
  --user_id demo_user \
  --session_id s1 \
  --device_id armband01 \
  --wearing_state normal \
  --duration_sec 45 \
  --clip_duration_sec 3 \
  --pre_roll_ms 500 \
  --port COM5 \
  --baudrate 115200 \
  --save_stream_csv
```

Cue logic for action labels:

- keep `CONTINUE` for about `0.4s`
- perform a fast, clear onset toward the target action
- return to `CONTINUE`
- do not try to maintain a continuous EMG hold

## Research Flow

The bounded research flow stays available for offline model selection:

```bash
python scripts/train_event_model_90_sprint.py \
  --stage all \
  --device_target Ascend \
  --device_id 0 \
  --data_dir ../data \
  --recordings_manifest recordings_manifest.csv \
  --run_prefix s2_model90
```

See `docs/model_90_sprint_runbook.md` for the full bounded search flow.

## Cloud And Pi Standard Flow

Production v1 uses a manual split:

- Huawei Cloud / high-performance machine: `prepare -> finetune -> convert -> evaluation -> release bundle`
- Orange Pi: `collect -> session bundle -> deploy release bundle -> runtime -> actuator`

There is no auto-upload or auto-deploy service in `master`. The supported path is a fixed manual standard flow.

### Current Artifact Roles

Do not mix the two archived artifact roles:

- preferred deploy baseline: `scr22`
- cloud release-flow validation sample: `smoke_release_s3_bg`

Use `scr22` when the goal is the strongest currently archived online-control deployment candidate.
Use `smoke_release_s3_bg` when the goal is proving that the manual Huawei Cloud release flow works end to end.

Supporting notes:

- `docs/cloud_release_v1_notes.md`
- `docs/pi_recovery_runbook.md`

### Export Minimal Bundles

Cloud-side bundle:

```bash
python scripts/export_event_cloud_bundle.py \
  --output artifacts/bundles/event_cloud_bundle.zip
```

Pi-side bundle:

```bash
python scripts/export_event_pi_bundle.py \
  --output artifacts/bundles/event_pi_bundle.zip
```

### Package One Pi Session

After a Pi-side collection session, package only that session:

```bash
python scripts/package_event_session_bundle.py \
  --data_dir ../data \
  --recordings_manifest recordings_manifest.csv \
  --session_id s1 \
  --output artifacts/bundles/session_s1.zip
```

The session bundle contains:

- `recordings_manifest.csv`
- `session_metadata.json`
- `data/<relative_path>` clip CSVs referenced by that session

### Run The Fixed Cloud Release Flow

Routine deployment should use the single cloud release flow instead of the research `--stage all` pipeline:

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

This flow produces:

- one training run
- one converted `MindIR + metadata`
- one `release_summary.json`
- one deployable release bundle

### Deploy The Release Bundle On Orange Pi

```bash
python scripts/deploy_event_release_bundle.py \
  --bundle artifacts/bundles/release_s1_release_bundle.zip
```

Deployment keeps a rollback copy under `deploy_backups/` before replacing:

- `models/event_onset.mindir`
- `models/event_onset.model_metadata.json`
- `configs/runtime_event_onset.yaml`
- `configs/event_actuation_mapping.yaml`

Pi recovery and live-smoke steps are fixed in:

- `docs/pi_recovery_runbook.md`

## Finetune And Convert

Direct finetune:

```bash
python scripts/finetune_event_onset.py \
  --config configs/training_event_onset.yaml \
  --data_dir ../data \
  --recordings_manifest ../data/recordings_manifest.csv \
  --run_root artifacts/runs \
  --run_id event_finetune_v1
```

Convert to MindIR:

```bash
python scripts/convert_event_onset.py \
  --config configs/conversion_event_onset.yaml \
  --checkpoint artifacts/runs/event_finetune_v1/checkpoints/event_onset_best.ckpt \
  --run_root artifacts/runs \
  --run_id event_convert_v1
```

Converted metadata exposes `CONTINUE` as the public background label.

## Runtime

Recommended runtime:

```bash
python scripts/run_event_runtime.py \
  --config configs/runtime_event_onset.yaml \
  --backend lite
```

Standalone smoke:

```bash
python scripts/run_event_runtime.py \
  --config configs/runtime_event_onset.yaml \
  --backend lite \
  --standalone \
  --duration_sec 10
```

If the selected backend artifact is missing, runtime exits immediately. There is no silent fallback.

## Pi Runtime And Safety Preset

The Pi runtime uses the frozen demo3 mainline and the `test_py_v1` safety preset derived from `/home/HwHiAiUser/ICT/test.py`:

- `TENSE_OPEN -> open`
- `THUMB_UP -> handshake`
- `WRIST_CW -> wrist clockwise latch (0° side, neutral=120°)`

`OK` and `peace` remain optional safety-test poses and are not part of the default demo3 runtime contract.

App-facing control semantics are frozen in `docs/app_control_contract.md`.

Required Pi-side system Python packages:

- `numpy`
- `scipy`
- `pyyaml`
- `pyserial`
- `smbus2`
- `mindspore_lite`

Use the `cp310 linux_aarch64` `mindspore_lite` wheel on Orange Pi. Do not install full `mindspore` for the edge runtime path.

## Release Validation

Release validation is the frozen acceptance flow:

1. convert `CKPT -> MindIR + metadata`
2. run `ckpt` control eval
3. run `lite` control eval
4. run real prosthesis live smoke

```bash
python scripts/validate_event_release.py \
  --candidate_run_id s3_demo3_release \
  --runtime_config configs/runtime_event_onset.yaml \
  --convert_device_target Ascend \
  --eval_device_target CPU \
  --port COM5
```

Release validation writes one `release_validation_summary.json` and keeps the smoke-test record structure fixed.

## Known Boundary

This repository does not promise continuous real-time mirroring of every subtle hand pose detail. The supported target is discrete command switching with stable hold and explicit gesture-to-gesture switching.

## Preflight

```bash
python scripts/preflight.py --mode local --wearer_data_dir ../data
python scripts/preflight.py --mode ascend --wearer_data_dir ../data
```

## Repository Hygiene

Do not commit generated outputs:

- `code/artifacts/runs/**`
- `code/artifacts/splits/*.json`
- `**/__pycache__/`
- `*.pyc`
- `.ipynb_checkpoints/`
- `.tmp_pytest*`
