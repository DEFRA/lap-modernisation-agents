---
mode: migration-delivery
description: Build and test stage: incremental code and tests per task
---
Run the **build** stage for the current story using the `build-engineer` sub-agent, following the stage loop in `.github/agents/migration-delivery.agent.md`.

1. `python .github/scripts/mda.py setup status` - if `missing` is non-empty, ask for every item and hold.
2. `python .github/scripts/mda.py stage start --stage build` - if it exits 3, tell the developer what is blocking (setup / unapproved prerequisite) and ask; do not proceed.
3. Delegate to `build-engineer` with the story ID, cycle, trigger, `paths` and artifact path from step 2.
4. `python .github/scripts/mda.py gate submit --stage build --summary "<summary>"`, then STOP and present the result. Wait for the developer to reply `approve` or `request changes: <text>`. Do not approve on their behalf.
