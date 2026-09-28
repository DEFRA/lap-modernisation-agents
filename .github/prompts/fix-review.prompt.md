---
mode: migration-delivery
description: Post-PR fix (pr-review): additional commit on the existing PR, developer-initiated only
---
Run the **build** stage for the current story using the `build-engineer` sub-agent, following the stage loop in `.github/agents/migration-delivery.agent.md`.

0. Developer-initiated reopen: `python .github/scripts/mda.py story reopen --trigger pr-review --reason "<why>"` (exit 3 => tell the developer and stop).
1. `python .github/scripts/mda.py setup status` - if `missing` is non-empty, ask for every item and hold.
2. `python .github/scripts/mda.py stage start --stage build --trigger pr-review` - if it exits 3, tell the developer what is blocking (setup / unapproved prerequisite) and ask; do not proceed.
3. Delegate to `build-engineer` with the story ID, cycle, trigger, `paths` and artifact path from step 2.
   Ask the developer to paste/describe the reviewer comments; scope is only those. Land as an additional commit on the existing PR, never a new PR.
4. `python .github/scripts/mda.py gate submit --stage build --summary "<summary>"`, then STOP and present the result. Wait for the developer to reply `approve` or `request changes: <text>`. Do not approve on their behalf.
