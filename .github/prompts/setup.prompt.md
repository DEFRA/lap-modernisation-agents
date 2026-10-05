---
mode: migration-delivery
description: Set up (or resume) a story: ADO project, story ID, legacy path, account, telemetry check
argument-hint: "Optional: ADO user story ID"
---
Run the setup procedure in `.github/agents/migration-delivery.agent.md` (Setup section), one question at a time:

1. `python .github/scripts/mda.py setup status`; `python .github/scripts/mda.py setup prereqs`; `python .github/scripts/mda.py setup pat`.
2. Ask which **ADO project** this story belongs to (one of the configured projects) and the story ID, then `python .github/scripts/mda.py setup set --project "<name>" --story-id <id>`. An `unknown_ado_project` answer lists the allowed names.
3. Ask: migration project? legacy (old) codebase path, new codebase path, HLD / HLSA / LLD paths -> `python .github/scripts/mda.py setup set --migration yes --old <p> --new <p> --hld <p> --hlsa <p> --lld <p>`.
4. Ask for the **application name** and **technology stack** (they head the efficiency report) -> `python .github/scripts/mda.py setup set --application "<name>" --tech-stack "<stack>"`.
5. `python .github/scripts/mda.py setup accounts`, show every account found, ask which to attribute to, then `python .github/scripts/mda.py setup confirm-account --login <chosen>`.
6. Check token telemetry: `python .github/scripts/mda.py setup otel`. If it says `file_missing`, show the developer the settings in `.github/docs/mda/otel-setup.md`, ask them to enable them, run one chat turn, and re-check. Without it the report shows tokens as UNAVAILABLE; say so plainly, do not hide it.
7. Ask the run mode (auto-continue yes/no) -> `python .github/scripts/mda.py setup set --auto-continue yes|no`.
