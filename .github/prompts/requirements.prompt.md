---
mode: migration-delivery
description: Requirements stage: read the ADO story, produce summary and scope
argument-hint: <story-id>
---
Run the **requirements** stage for the current story using the `requirements-agent` sub-agent, following the stage loop in `.github/agents/migration-delivery.agent.md`.

1. `python .github/scripts/mda.py setup status` - if `missing` is non-empty, ask for every item and hold.
2. `python .github/scripts/mda.py stage start --stage requirements` - if it exits 3, tell the developer what is blocking (setup / unapproved prerequisite) and ask; do not proceed.
3. Delegate to `requirements-agent` with the story ID, cycle, trigger, `paths` and artifact path from step 2.
   If `$ARGUMENTS` gives a story ID and none is bound, run setup first (`setup set --story-id`).
4. `python .github/scripts/mda.py gate submit --stage requirements --summary "<summary>"`, then STOP and present the result. Wait for the developer to reply `approve` or `request changes: <text>`. Do not approve on their behalf.
