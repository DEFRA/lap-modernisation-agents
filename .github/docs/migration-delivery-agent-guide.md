# Migration Delivery Agent Guide

- **Current version:** v1 — see [agent-versioning-strategy.md](agent-versioning-strategy.md)
- **Version folders:** `.github/agents/versions/<agent-name>/v1/` (one per agent below)
- **Creating v2+:** add `.github/agents/versions/<agent-name>/v2/` with a README (owner, scope, differences, migration guidance) and implement the change there; do not edit v1.
- **How it works, data model, dashboards and efficiency:** [mda/how-it-works-and-data-guide.md](mda/how-it-works-and-data-guide.md)
- **Copilot CLI vs. VS Code Chat dropdown — what's enforced in each:** [mda/runtimes.md](mda/runtimes.md)
- **Build progress / named gaps:** [mda/build-checklist.md](mda/build-checklist.md)

## What it is

An agentic workflow on GitHub Copilot CLI's agent / prompt / hook architecture that takes one migration user story from intake to release with a **human approval gate at every stage**, and records effort, token use and complexity durably to Azure DevOps (ADO) for Wiki narrative and dashboards.

| Piece | Location |
|---|---|
| Orchestrator + 8 sub-agents | `.github/agents/migration-delivery.agent.md`, `requirements-agent`, `legacy-analyst`, `target-architect`, `build-engineer`, `quality-gate-agent`, `release-packager`, `qa-authoring-agent`, `reporting-agent` |
| Commands (`/requirements`, `/discover`, `/plan`, `/build`, `/quality-check`, `/package-pr`, `/fix-review`, `/fix-sonar`, `/qa-author`, `/generate-report`, `/approve`, `/request-changes`, `/qa-log-execution`) | `.github/prompts/` |
| Hooks (all events → one dispatcher) | `.github/hooks/mda-hooks.json`, `.github/hooks/scripts/mda_hook.py` |
| Core library (stdlib-only Python 3.9+) | `.github/lib/mda/` |
| CLI the agents call | `.github/scripts/mda.py` |
| Skills | `.github/skills/migration-delivery/` |
| Config | `.github/config/mda/mda.config.json`, `complexity-model.json` |
| Excel export + Wiki append pipeline | `.github/pipelines/mda-effort-export.yml`, `.github/scripts/pipeline/export_effort_excel.py` |
| Tests | `tests/mda/` — `python -m unittest discover -s tests/mda -v` |

## Getting started

1. Set environment (never commit): `MDA_ADO_PAT` (scopes: Work Items read & write, Wiki read & write, Analytics read), `MDA_ADO_PAT_EXPIRY=YYYY-MM-DD`, `MDA_ADO_ORG_URL`, `MDA_ADO_PROJECT`. Windows and macOS step-by-step: [mda/environment-setup.md](mda/environment-setup.md).
2. **Optional**, not required to run: create the Effort Record custom fields in ADO — see [mda/ado-setup.md](mda/ado-setup.md). Every record is written as full JSON either way (into the custom fields if they exist, otherwise into the work item's Description); skipping this step only means you cannot yet build native ADO/Power BI charts grouped by tier, developer, sprint, etc.
3. Run `python .github/scripts/mda.py ado check` to verify the PAT and scopes.
4. Start Copilot CLI in the repo, select `migration-delivery`, and give it the story ID. It will hold until setup is complete, and ask whether to **auto-continue** (run all stages one by one, pausing at each approval) or run one command at a time. See [mda/how-it-works-and-data-guide.md](mda/how-it-works-and-data-guide.md).

## How the pieces guarantee the rules

| Rule | Mechanism |
|---|---|
| Setup blocks pipeline | `stage start` refuses while anything is missing; the tool-gate hook denies write/shell tools until setup is complete |
| Agent can't approve itself | No approve verb exists. The `userPromptSubmitted` hook records `approve` / `request changes: …` from the developer's own prompt |
| Agent can't proceed past a gate | Tool-gate hook denies edits/shell while a stage is `awaiting_approval` (read-only tools and `mda.py` stay allowed) |
| Agent can't skip submitting | `agentStop` hook blocks and forces continuation (max 2 times per stage) if a stage run is open and unsubmitted; `subagentStop` does the same for a missing artifact |
| Effort never = last − first | Only bounded intervals are stored: AI turn (`userPromptSubmitted` → `agentStop`) plus approval gap (`approval − last agent response`). Sub-agent intervals are breakdown only (no double count) |
| Idle protection | Any turn or approval gap over the cap (default 120 min) is truncated and flagged `capped` — see open items |
| Crash resilience | Local JSON (checksummed, `.bak` copy) is a cache; synced to ADO on every gate event, opportunistic heartbeat (5 min), and every Nth prompt drift check; corrupt/missing → rebuilt from ADO |
| Self-heal cap | `postToolUseFailure` counts; at cap (default 3) tools are denied until the developer speaks |

## Cycles

`cycle` increments only when a story is reopened after being marked complete (dev checkpoint after PR, QA `reopen`, or a post-PR fix). A reopen before completion re-enters Build → Quality in the same cycle. History is always appended to the same story ID. Triggers: `pr-review`, `sonar-recheck`, `qa-defect`, `dev-reopen`.

## Data in ADO

One **Effort Record** work item per `(story, cycle, stage, phase)` (title `MDA-<story>-c<cycle>-<stage>-<phase>`, tag `MDA-EffortRecord`, child of the story), plus one `MDA-<story>-state` record holding the full JSON snapshot used for recovery. **The complete JSON payload is always written**, whether or not the custom fields (below) exist: with them it also lands in individual structured fields for querying; without them the same JSON is written into the work item's Description instead — no data is lost either way, only queryability changes. Raw complexity factor counts **and** weights are stored on every row alongside tier, traditional-day estimate, measured effort, calendar duration, confirmed developer account, tokens and timestamp. Developer-level Copilot usage is stored as `MDA-usage-<login>-<date>` records.

## Open governance items (spec §15)

See [mda/build-checklist.md](mda/build-checklist.md#open-governance-items).
