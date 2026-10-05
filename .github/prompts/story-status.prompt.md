---
mode: migration-delivery
description: Show where the story is: stages, gate, cycle, sync state, telemetry
---
Run `python .github/scripts/mda.py story status`, `python .github/scripts/mda.py gate status` and `python .github/scripts/mda.py session`. Present stage statuses, which gate (if any) awaits approval, the cycle and trigger, when ADO was last synced (and whether data is dirty), and any warnings. Do not change anything.
