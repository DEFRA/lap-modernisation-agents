---
mode: migration-delivery
description: Resume a story (from the local cache or, if missing, recovered from ADO)
argument-hint: <ADO user story ID>
---
1. `python .github/scripts/mda.py story resume --id $ARGUMENTS`. If the local cache is missing or corrupt, use `python .github/scripts/mda.py story recover --id $ARGUMENTS --project "<ado project>"` (it merges every developer's last synced state).
2. `python .github/scripts/mda.py setup status`. Setup is per story: do not re-ask what is already captured; ask only for what is missing.
3. Show `python .github/scripts/mda.py story status` and offer the next command.
