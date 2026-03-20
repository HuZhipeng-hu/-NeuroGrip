# App Control Contract

Frozen public action labels:

- `CONTINUE`
- `TENSE_OPEN`
- `THUMB_UP`
- `WRIST_CW`

Behavior contract:

- `CONTINUE`: keep the current latched prosthesis state
- `TENSE_OPEN`: switch to the fully open hand pose and latch
- `THUMB_UP`: switch to the thumb-up pose and latch
- `WRIST_CW`: switch to the clockwise wrist pose and latch

State transitions:

- `CONTINUE` never unlocks or releases a latched state
- switching to another gesture is the only way to leave the current state
- `THUMB_UP -> TENSE_OPEN` is the explicit "open" transition
- `WRIST_CW -> TENSE_OPEN` returns the wrist to neutral and opens the hand

Internal compatibility note:

- runtime internals still normalize both `CONTINUE` and legacy `RELAX`
- App integrations must only use the public label `CONTINUE`
