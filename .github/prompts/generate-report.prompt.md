---
mode: migration-delivery
description: Generate the effort, token and complexity report (callable any time)
---
Delegate to `reporting-agent`: `python .github/scripts/mda.py sync push`, then `python .github/scripts/mda.py report --print` (add `--wiki` only if the developer asks to append to the ADO Wiki). Relay the report with its caveats (uncalibrated model, idle-capped intervals, estimated tokens, QA manual execution shown separately).
