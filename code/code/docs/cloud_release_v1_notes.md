# Cloud Release V1 Notes

## Purpose

This note separates two different artifact roles that now coexist in the local archive:

- the preferred deploy candidate for the current demo3 prosthesis runtime
- the manual cloud release-flow validation sample that proves the end-to-end cloud path works

These are not the same thing and should not be mixed during deployment.

## Preferred Deploy Candidate

Current preferred deploy baseline:

- candidate id: `s3_demo3_0317_scr_tuned_scr_22_lcb_focal_bc16_fz8_elr0p24_ptoff`
- local checkpoint: `checkpoints/event_onset_scr22_best.ckpt`
- local MindIR: `models/event_onset_scr22.mindir`
- local metadata: `models/event_onset_scr22.model_metadata.json`
- local runtime source config: `configs/runtime_event_onset_scr22_source.yaml`

Reason this remains the preferred deploy baseline:

- `command_success_rate = 0.9411764705882353`
- `false_trigger_rate = 0.058823529411764705`
- `false_release_rate = 0.0`
- `lite` parity was already validated

This candidate is the stronger online-control choice and should stay the default deployment reference until a later candidate is both stronger and verified on the real prosthesis chain.

## Cloud Release-Flow Validation Sample

Validated manual cloud release-flow sample:

- run id: `smoke_release_s3_bg`
- local archive: `artifacts/cloud_sync_20260319_release_v1/`
- release bundle archive: `artifacts/cloud_sync_20260319_release_v1/smoke_release_s3_bg.zip`

What this sample proves:

- session bundle unpacking works
- cloud finetune works
- `CKPT -> MindIR` conversion works
- `ckpt/lite` parity report is produced
- deployable release bundle generation works

Key metrics for this sample:

- `event_action_accuracy = 0.8717948717948718`
- `command_success_rate = 0.6896551724137931`
- `false_trigger_rate = 0.2413793103448276`
- `false_release_rate = 0.16666666666666666`
- parity: passed

This sample is retained as process evidence, not as the preferred online-control deployment model.

## Local Evidence Layout

Preferred deploy candidate evidence:

- `artifacts/cloud_sync_20260318/scr22_candidate/`
- `artifacts/cloud_sync_20260318/baseline_tuning/`

Cloud release-flow validation evidence:

- `artifacts/cloud_sync_20260319_release_v1/`

## Rule

Use:

- `scr22` when the goal is best currently archived deployment behavior
- `smoke_release_s3_bg` when the goal is proving the manual cloud release flow is complete and reproducible

Do not automatically replace the deploy baseline with `smoke_release_s3_bg` just because the cloud release-flow sample is newer.
