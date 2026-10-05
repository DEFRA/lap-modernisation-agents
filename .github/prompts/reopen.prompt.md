---
mode: migration-delivery
description: Reopen a story after PR review, a Sonar recheck, a QA defect, or a developer decision
argument-hint: "pr-review|sonar-recheck|qa-defect|dev-reopen <reason>"
---
Developer-initiated only (never off a CI failure or a review comment landing by itself).
1. Confirm the trigger and the reason with the developer.
2. `python .github/scripts/mda.py story reopen --trigger <trigger> --reason "<why>"`. Re-entry runs Build then Quality in full; the cycle increments only if the story had been marked complete.
3. Offer `/build` (or `/fix-review` / `/fix-sonar`).
