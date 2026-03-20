# Orange Pi Recovery Runbook

Use this runbook after Orange Pi network access returns. It assumes:

- current Pi user: `HwHiAiUser`
- project root on Pi: `/home/HwHiAiUser/ICT`
- release bundle is prepared on another machine first
- Pi is used only for collection, deployment, inference, and prosthesis control

## 1. Verify Basic Access

From the operator machine:

```bash
ping 192.168.238.55
ssh HwHiAiUser@192.168.238.55
```

## 2. Check System Python

On the Pi:

```bash
python3 --version
python3 - <<'PY'
mods = ["numpy", "yaml", "serial", "smbus2", "mindspore_lite"]
for name in mods:
    try:
        __import__(name)
        print(name, "ok")
    except Exception as exc:
        print(name, "missing", exc.__class__.__name__)
PY
```

Required Pi runtime packages:

- `numpy`
- `scipy`
- `pyyaml`
- `pyserial`
- `smbus2`
- `mindspore_lite`

Notes:

- Pi should not install the full `mindspore` training package
- the old `cp39` Lite wheel is not valid for Python `3.10`
- use the official `mindspore_lite-2.7.1-cp310-cp310-linux_aarch64.whl`

## 3. Install Missing Runtime Dependencies

Example commands:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install numpy scipy pyyaml pyserial smbus2
python3 -m pip install /path/to/mindspore_lite-2.7.1-cp310-cp310-linux_aarch64.whl
```

## 4. Unpack Pi Bundle

Copy the Pi bundle to the Pi, then:

```bash
mkdir -p ~/ICT/runtime_bundle
unzip -o event_pi_bundle.zip -d ~/ICT/runtime_bundle
```

## 5. Verify Safe Servo Motions Against `test.py`

Before running the main runtime, compare the verified safe actions from:

- `/home/HwHiAiUser/ICT/test.py`

Current intended safe mappings in the mainline runtime:

- `TENSE_OPEN -> open`
- `THUMB_UP -> handshake`
- `WRIST_CW -> clockwise wrist latch (0° side, neutral=120°)`
- `CONTINUE -> no new actuation command`

Do not run unverified servo angle tables on the real prosthesis first.

## 6. Deploy Release Bundle

Copy the chosen release bundle to the Pi, then:

```bash
cd /home/HwHiAiUser/ICT/runtime_bundle/code
python3 scripts/deploy_event_release_bundle.py \
  --bundle /path/to/release_bundle.zip
```

This should:

- validate bundle contents
- copy new runtime/model files into place
- preserve rollback files under `deploy_backups/`

## 7. Start Lite Runtime

Example:

```bash
cd /home/HwHiAiUser/ICT/runtime_bundle/code
python3 scripts/run_event_runtime.py \
  --config configs/runtime_event_onset.yaml \
  --backend lite
```

## 8. Real Prosthesis Smoke

Only after the safe-action mapping has been confirmed.

Target acceptance:

- `TENSE_OPEN`: 5 trials, at least 4 successful
- `THUMB_UP`: 5 trials, at least 4 successful
- `WRIST_CW`: 5 trials, at least 4 successful
- `CONTINUE`: hold for 10 seconds with at most 1 false trigger

Frozen latch contract reminder:

- `CONTINUE` keeps the current state
- `TENSE_OPEN`, `THUMB_UP`, and `WRIST_CW` are all latched states
- leaving a latched state requires switching to another gesture

If any safe action mismatches the verified behavior from `test.py`, stop and fix the actuator mapping before continuing.

## 9. If Deployment Fails

Check:

- `models/event_onset.mindir`
- `models/event_onset.model_metadata.json`
- `configs/runtime_event_onset.yaml`
- `configs/event_actuation_mapping.yaml`
- `deploy_backups/`

If needed, restore the last known good bundle from `deploy_backups/` before testing again.
