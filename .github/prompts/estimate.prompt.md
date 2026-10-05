---
mode: migration-delivery
description: Show, adjust or confirm the traditional-effort estimate (person-days per phase) for the story
---
1. `python .github/scripts/mda.py estimate show` and present the per-phase table with its labels (LLM-estimated and unvalidated, not confirmed).
2. To adjust one phase: `python .github/scripts/mda.py estimate set --phase <p> --pd <n> --reason "<why>" --source llm|developer` (a reason is mandatory; the base figure is kept).
3. When the developer agrees: `python .github/scripts/mda.py estimate confirm`. Never confirm on the developer's behalf.
