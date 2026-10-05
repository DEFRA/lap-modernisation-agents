# Migration Delivery Agent Guide

- **Current version:** v1 — see [agent-versioning-strategy.md](agent-versioning-strategy.md)
- **Version folders:** `.github/agents/versions/<agent-name>/v1/` (one per agent below)
- **Creating v2+:** add `.github/agents/versions/<agent-name>/v2/` with a README (owner, scope, differences, migration guidance) and implement the change there; do not edit v1.
- **How it works, data model, dashboards and efficiency:** [mda/how-it-works-and-data-guide.md](mda/how-it-works-and-data-guide.md)
- **Copilot CLI vs. VS Code Chat dropdown — what's enforced in each:** [mda/runtimes.md](mda/runtimes.md)
- **Programme-level Benefits / Delivery Comparison report (Effort/Time/Cost saving, PD vs. Days):** [mda/benefits-report.md](mda/benefits-report.md)
- **Start here, step by step (ADO setup, machine setup, every command, the pipeline, the Excel):** [mda/getting-started.md](mda/getting-started.md)

## What it is

An agentic workflow on GitHub Copilot CLI's agent / prompt / hook architecture that takes one migration user story from intake to release with a **human approval gate at every stage**, and records effort, token use and complexity durably to Azure DevOps (ADO) for Wiki narrative and dashboards.

| Piece | Location |
|---|---|
| Orchestrator + sub-agents | `.github/agents/migration-delivery.agent.md`, `requirements-agent`, `legacy-analyst`, `target-architect`, `build-engineer`, `quality-gate-agent`, `release-packager`, `qa-authoring-agent`, `reporting-agent`, `research-agent` (new); reuses `db-migration`, `dotnet-test-automation-and-quality-agent`, `security-code`, `documentation-lld` for the activity commands |
| Commands: gated stages (`/requirements`, `/discover`, `/plan`, `/build`, `/quality-check`, `/package-pr`, `/qa-author`), re-entry (`/fix-review`, `/fix-sonar`, `/reopen`), activities (`/research`, `/db-analysis`, `/unit-test`, `/security-review`, `/document`), and `/setup`, `/estimate`, `/log-manual`, `/story-status`, `/resume-story`, `/usage`, `/generate-report`, `/benefits-report`, `/approve`, `/request-changes`, `/qa-log-execution` | `.github/prompts/` |
| Hooks (all events → one dispatcher) | `.github/hooks/mda-hooks.json`, `.github/hooks/scripts/mda_hook.py` |
| Core library (stdlib-only Python 3.9+) | `.github/lib/mda/` |
| CLI the agents call | `.github/scripts/mda.py` |
| Skills | `.github/skills/migration-delivery/` |
| Config | `.github/config/mda/mda.config.json`, `complexity-model.json`, `benefits-model.json` (stage to phase) |
| AI Efficiency Excel pipeline (per ADO project, optional date range) | `.github/pipelines/mda-ai-efficiency-report.yml`, `.github/scripts/pipeline/export_ai_efficiency.py`, `.github/lib/mda/xlsx.py` |
| Real token usage (Copilot OpenTelemetry) | `.github/lib/mda/otel.py`, [mda/otel-setup.md](mda/otel-setup.md) |
| Tests | `tests/mda/` — `python -m unittest discover -s tests/mda -v` |

## Getting started

1. Set environment (never commit): `MDA_ADO_PAT` (scopes: Work Items read & write, Wiki read & write, Analytics read), `MDA_ADO_PAT_EXPIRY=YYYY-MM-DD`, `MDA_ADO_ORG_URL`, `MDA_ADO_PROJECT`. Windows and macOS step-by-step: [mda/getting-started.md](mda/getting-started.md) (Part B).
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

Work items in the **story's own ADO project** (tag `MDA-EffortRecord`, children of the user story): one **effort record per developer, work date and stage** (`MDA-<story>-<developer>-<date>-c<cycle>-<stage>`), one `MDA-<story>-estimate` record (traditional estimate, tier, factor counts, application and stack), and one `MDA-<story>-state-<developer>` recovery snapshot per developer (recovery merges them). **The complete JSON payload is always written**, with or without the optional custom fields; without them it goes into the Description. Full detail, field list and where to create the work items: [mda/ado-setup.md](mda/ado-setup.md). The AI Efficiency Excel for any date range is built from these records by the `mda-ai-efficiency-report` pipeline ([mda/benefits-report.md](mda/benefits-report.md)); real token counts come from Copilot OpenTelemetry ([mda/otel-setup.md](mda/otel-setup.md)).

## Open governance items (spec §15)

Open items that need a decision or a live check (idle limits, hook wiring, OpenTelemetry format, ADO fields) are listed in [mda/getting-started.md](mda/getting-started.md) (Part E) and [mda/runtimes.md](mda/runtimes.md).
