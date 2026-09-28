---
mode: migration-delivery
description: Commit and PR packaging: categorized commits and PR description from the repo template
---
Run the **pr** stage for the current story using the `release-packager` sub-agent, following the stage loop in `.github/agents/migration-delivery.agent.md`.

1. `python .github/scripts/mda.py setup status` - if `missing` is non-empty, ask for every item and hold.
2. `python .github/scripts/mda.py stage start --stage pr` - if it exits 3, tell the developer what is blocking (setup / unapproved prerequisite) and ask; do not proceed.
3. Delegate to `release-packager` with the story ID, cycle, trigger, `paths` and artifact path from step 2.
   The developer pushes and opens the PR; afterwards run `python .github/scripts/mda.py story pr-raised --url <url> --number <n>` and ask whether the story is complete from a dev perspective (`story complete --answer yes|no`).
4. `python .github/scripts/mda.py gate submit --stage pr --summary "<summary>"`, then STOP and present the result. Wait for the developer to reply `approve` or `request changes: <text>`. Do not approve on their behalf.
