---
name: migration-delivery-complexity-scoring
description: How the plan stage turns discovery counts into a complexity tier and an LLM-estimated traditional effort (person-days per phase), and what the developer confirms at the plan gate.
---

# Plan stage: score and estimate

Two separate outputs. Neither is computed by hand and neither is presented as measured.

1. **Complexity tier** - `mda.py complexity score`: weighted points, tier, traditional-day range, assumed efficiency. The model is UNCALIBRATED until `mda.py complexity calibrate` has been run against 10-15 completed stories.
2. **Traditional estimate** - your judgement, recorded with `mda.py estimate set`. There is no rate card. For each of Discovery, Design, Build and Test, estimate the person-days the story would take to deliver the traditional (non-AI) way, with a one-sentence reason grounded in the discovery evidence (counts, code paths, integrations) and the design. The tier's `traditional_days` range is a sanity anchor only: if your phases sum far outside it, say why in the reasons.

## Recording
`python .github/scripts/mda.py estimate set --source llm --json '{"discovery":{"pd":N,"reason":"..."},"design":{...},"build":{...},"test":{...}}'`

Transition to Live and Support have no pipeline stage; leave them out unless the developer gives a figure (`estimate set --phase transition_to_live --pd N --reason "..." --source developer`).

## At the plan gate, present
- the tier and the score breakdown;
- the estimate table (PD, reason and source per phase) with its labels (LLM-estimated and unvalidated, not confirmed) and any phase that shows NEEDS INPUT.

## Adjusting and confirming
- The developer can change any phase: `estimate set --phase <p> --pd <n> --reason "<why>" --source developer`. A written reason is mandatory; any change resets confirmation.
- When the developer agrees: `mda.py estimate confirm` (records who and when, and syncs to ADO). Never confirm for them.

## Rules
- Do not fake precision: round to the nearest half day.
- Uncalibrated tier and LLM-estimated effort are internal-use-only and must not be described as client-facing.
- The 40% efficiency baseline is an assumption, not a measurement.
