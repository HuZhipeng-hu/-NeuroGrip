# Deployment Runbook

This runbook describes the Kunpeng Pro deployment path for the NeuroGrip Demo3 baseline.

## 1. Kunpeng Pro Runtime Dependencies

Required Python packages:

- `numpy`
- `scipy`
- `pyyaml`
- `pyserial`
- `smbus2`
- `mindspore_lite`

Example installation:

```bash
python3 -m pip install numpy scipy pyyaml pyserial smbus2
python3 -m pip install /path/to/mindspore_lite-2.7.1-cp310-cp310-linux_aarch64.whl
```

## 2. Baseline Files Used By Deployment

The included baseline model files are:

- `checkpoints/event_onset_best.ckpt`
- `models/event_onset.mindir`
- `models/event_onset.model_metadata.json`

Kunpeng Pro runtime should use:

- `configs/runtime_event_onset_kunpeng_pro.yaml`

This configuration file reflects the verified live runtime settings used for the final Kunpeng Pro hardware smoke.

## 3. Start The Runtime

```bash
python3 scripts/run_event_runtime.py \
  --config configs/runtime_event_onset_kunpeng_pro.yaml \
  --backend lite
```

## 4. Actuation Mapping

The default action mapping is defined in:

- `configs/event_actuation_mapping.yaml`

The current deployment path controls:

- `TENSE_OPEN`
- `V_SIGN`
- `THUMB_UP`
- `WRIST_CW`
- `CONTINUE`

## 5. Live Runtime Notes

The current Kunpeng Pro runtime configuration uses:

- serial port: `/dev/ttyUSB0`
- PCA9685 I2C bus: `7`
- hand channels: `[0, 2, 4, 3, 1]`
- wrist channel: `5`
- safety preset: `test_py_v1`

These values can be adjusted in `configs/runtime_event_onset_kunpeng_pro.yaml` to match the actual device wiring.

The package also includes the latest live runtime verification logs under:

- `artifacts/runtime_sessions/20260321_220737_event_runtime/`
