---
mode: migration-delivery
description: Generate or update the LLD / design documentation for the story from HLD and HLSA
argument-hint: "<what to look at>"
---
Run the **document** activity for the current story with the `documentation-lld` agent. It has no approval gate of its own, but its time is booked to the stage it belongs to, so always bracket it.

1. `python .github/scripts/mda.py setup status` - if `missing` is non-empty, ask for every item and hold (run `/setup`).
2. `python .github/scripts/mda.py activity start --name document` (exit 2 means an unknown activity; stop).
3. Delegate to `documentation-lld` with the story ID, cycle, the `paths` from setup and the request in `$ARGUMENTS`. Write findings to `docs/mda/<story-id>/document.md`.
4. `python .github/scripts/mda.py activity end` (always, even if the work failed or was cut short).
5. Summarise what was found and where it is saved. Anything that changes the plan or estimate goes to the developer at the next gate; do not approve or advance a stage from here.
