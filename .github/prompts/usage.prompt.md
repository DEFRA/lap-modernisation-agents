---
mode: migration-delivery
description: Snapshot the developer's GitHub Copilot premium-request usage (billing figure, not tokens)
---
Run `python .github/scripts/mda.py usage`. Present the month-to-date premium requests and the change since the last snapshot. This is a per-developer billing figure from GitHub, not story-level and not tokens; story tokens come from the OpenTelemetry import.
