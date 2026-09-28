---
mode: migration-delivery
description: Architecture and plan stage: design, test plan, complexity tier and day estimate
---
Run the **plan** stage for the current story using the `target-architect` sub-agent, following the stage loop in `.github/agents/migration-delivery.agent.md`.

1. `python .github/scripts/mda.py setup status` - if `missing` is non-empty, ask for every item and hold.
2. `python .github/scripts/mda.py stage start --stage plan` - if it exits 3, tell the developer what is blocking (setup / unapproved prerequisite) and ask; do not proceed.
3. Delegate to `target-architect` with the story ID, cycle, trigger, `paths` and artifact path from step 2.
   Present the complexity score at the gate for the developer to confirm or adjust.
4. `python .github/scripts/mda.py gate submit --stage plan --summary "<summary>"`, then STOP and present the result. Wait for the developer to reply `approve` or `request changes: <text>`. Do not approve on their behalf.
