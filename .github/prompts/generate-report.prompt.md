---
mode: migration-delivery
description: Generate the effort, token and complexity report (callable any time)
---
Delegate to `reporting-agent`: `python .github/scripts/mda.py sync push`, then `python .github/scripts/mda.py report --print` (add `--wiki` only if the developer asks to append to the ADO Wiki). The report imports the latest OpenTelemetry token data first. Relay it with its caveats: uncalibrated model, LLM-estimated traditional effort, idle gaps excluded, tokens UNAVAILABLE when telemetry is off, QA manual execution shown separately.
