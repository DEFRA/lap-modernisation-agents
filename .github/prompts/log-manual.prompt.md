---
mode: migration-delivery
description: Log manual (non-AI) effort for Transition to Live or Support, with minutes and a note
argument-hint: "transition_to_live|support <minutes>"
---
Manual effort for phases the agent does not run.

1. Ask which phase (`transition_to_live` or `support`), the minutes, a one-line note, and the date if it was not today.
2. `python .github/scripts/mda.py manual log --phase <phase> --minutes <N> --note "<what>" [--date YYYY-MM-DD]`.
3. Optionally record the **traditional** figure for that phase for this story: `python .github/scripts/mda.py estimate set --phase <phase> --pd <N> --reason "<why>" --source developer`, then `python .github/scripts/mda.py estimate confirm`.
Report it as manual effort; there is no AI-efficiency claim for it.
