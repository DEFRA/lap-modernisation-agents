---
mode: migration-delivery
description: Log manual QA execution time or record the QA outcome (no AI involved)
---
Ask for minutes spent and run `python .github/scripts/mda.py qa log-execution --minutes N --note "<what>"`. For the outcome run `python .github/scripts/mda.py qa outcome --result pass` (closes the story) or `--result reopen --reason "<defect>"` (next cycle, tagged qa-defect). Manual execution is reported as a separate line with no AI-efficiency claim.
