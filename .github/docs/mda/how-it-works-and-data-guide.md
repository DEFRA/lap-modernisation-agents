# Migration Delivery Agent: how it works, what it records, how to report on it

Audience: developers who run stories through the agent, and the team lead who builds dashboards and tracks efficiency. The JSON samples below are real output from a simulated story (values shortened where noted).

---

## 0. Which runtime are you in?

This whole document describes the design's strongest mode: running via **GitHub Copilot CLI**, where hooks time and enforce things automatically. If you instead select the `migration-delivery` agent from the **VS Code Copilot Chat dropdown**, there is no hook layer, and the orchestrator self-drives timing and approval recording via explicit CLI calls instead — same data shape, softer guarantees. Read **[runtimes.md](runtimes.md)** first if you're unsure which applies; `python .github/scripts/mda.py session` tells you (`hooked: true/false`).

## 1. How it works in one page

```
 Developer chats in Copilot CLI                    Copilot CLI hooks (automatic)
 ────────────────────────────────                  ─────────────────────────────────────────
 /requirements 4521  ───────────────────────────►  userPromptSubmitted  starts the AI-time clock
        │                                          
        ▼                                          
 migration-delivery agent                          
   runs:  mda.py stage start   ─► checks setup + prerequisites, marks stage in_progress
   delegates to a sub-agent, which writes docs/mda/<story>/<stage>.md
   runs:  mda.py gate submit   ─► stage = awaiting_approval, pushes state to ADO
        │                                          agentStop  ends the AI-time clock, stores the interval
        ▼                                          (if the stage was never submitted: blocks and forces it to continue)
 Agent STOPS and asks you
        │
 You type:  approve   |   request changes: <text>
        │                                          userPromptSubmitted  sees YOUR words, records the approval,
        ▼                                          adds "approval - last agent response" as effort, syncs to ADO
 Next stage unlocks
```

Three layers:

| Layer | What it is | Who triggers it |
|---|---|---|
| **Agents and prompts** (`.github/agents`, `.github/prompts`) | The workflow: orchestrator, 8 sub-agents, `/plan`, `/build`, etc. | You, by typing commands in chat |
| **Hooks** (`.github/hooks/mda-hooks.json` → `mda_hook.py`) | Silent recorder and enforcer. Times every turn, blocks tools while a gate is open, records approvals, syncs to ADO | Copilot CLI, automatically on each event |
| **CLI** (`.github/scripts/mda.py`) | The only thing that changes state (stage start/submit, complexity, reopen…) | The **agent** runs it for you |

### Two ways to run it: auto-continue or one command at a time

At setup the agent asks once. The answer is stored on the story (`setup.auto_continue`), so it survives resumed sessions and new days.

| Mode | What you do | What the agent does |
|---|---|---|
| **Auto-continue ON** | Select the `migration-delivery` agent, give it the story ID. Type only `approve` / `request changes: …` at each gate | After each `approve` it starts the next stage itself: requirements → discovery → plan → build → quality → pr. Each stage still ends at its own gate |
| **Auto-continue OFF** (default) | Type the stage command yourself (`/discover`, `/plan`, …) | Runs that one stage, stops at the gate, offers the next command |

In both modes:
- Auto-continue never skips a gate or a prerequisite; a blocked result (exit 3), a failed tool cap or a request for changes stops the chain.
- The chain **ends after `pr`**. You push and open the PR; QA authoring, `/fix-review`, `/fix-sonar`, `/qa-log-execution` and `/generate-report` are always explicit commands.
- Change the mode any time by telling the agent ("turn auto-continue off"); it runs `mda.py setup set --auto-continue yes|no`. Check with `mda.py story status` (`auto_continue`, `next_auto_stage`).
- Typing a stage command in auto mode is fine, for example to re-run one stage; the chain then resumes from the next unapproved stage.

### Do I run Python scripts manually?

Day to day: **no.** You type slash commands and `approve`; the agent calls `mda.py` and the hooks run on their own. Manual steps are limited to:

| When | What | Who |
|---|---|---|
| One-off per machine | Set env vars `MDA_ADO_PAT`, `MDA_ADO_PAT_EXPIRY`, `MDA_ADO_ORG_URL`, `MDA_ADO_PROJECT` (never commit them) — Windows/macOS steps: [environment-setup.md](environment-setup.md) | Each developer |
| One-off per ADO org/project, **optional** | Create the Effort Record custom fields ([ado-setup.md](ado-setup.md)) so ADO/Power BI can query by field, not just recover the JSON; add sprint dates to `.mda/config.local.json` | Team lead |
| After setup (optional check) | `python .github/scripts/mda.py ado check` | Anyone |
| Any time | `/generate-report` in chat, or `python .github/scripts/mda.py report --print` / `metrics` | Anyone |
| Story reopens after PR | `/fix-review`, `/fix-sonar`, or tell the agent QA found a defect | Developer |
| After manual QA testing | `/qa-log-execution` (minutes spent) | QA / developer |
| Once you have 10–15 finished stories | `python .github/scripts/mda.py complexity calibrate --history history.csv` | Team lead |
| When you want the Excel + Wiki entry | Manually run the `mda-effort-export` ADO pipeline | Team lead |

Things the agent **cannot** do by design: approve a gate, push code, open the PR.

### What happens if something goes wrong

- **Laptop crash / corrupt local file**: local files carry a checksum and a `.bak`; on detection the agent rebuilds the story from the last state synced to ADO.
- **ADO unreachable**: work continues; the story is flagged `dirty` and retried at the next gate event, heartbeat (5 min) or session end. Hooks never break your session.
- **Tool keeps failing**: after 3 consecutive failures (configurable) edits/shell are denied until you reply, so the agent has to stop and ask.

---

## 2. Where the data lives

| Location | Content | Source of truth? |
|---|---|---|
| `.mda/stories/story-<id>.json` (local, git-ignored) | Everything about one story (below) | **No** – a cache |
| `.mda/sessions/<sessionId>.json` (local) | Scratch state for one Copilot session (open clock, active stage) | No |
| `.mda/usage/<login>.json` (local) | Daily Copilot premium-request snapshots | No |
| `docs/mda/<id>/*.md` | Stage artifacts written by the sub-agents (requirements, discovery, plan, …, `report.md`) | Yes (reviewable) |
| `docs/mda/<id>/usage-metrics.ndjson` | Dashboard feed in GitHub's user-level shape | Generated |
| **ADO Effort Record work items** | One row per story/cycle/stage/phase, one `-state` snapshot per story. Full JSON is always stored (in `Custom.MDAPayload` if the field exists, else in the work item Description) | **Yes** |
| ADO Wiki | Narrative reports, appended over time | Generated from the above |

---

## 3. The story file (`story-<id>.json`)

Top-level keys and what they hold:

| Key | Meaning |
|---|---|
| `project`, `story_id`, `created` | Identity. Must match ADO or the drift check stops the agent |
| `setup` | `is_migration`, code/doc paths, `account.confirmed_login` (who usage is attributed to), `auto_continue` (run mode), PAT check result |
| `cycle`, `complete`, `closed`, `current_trigger` | Cycle number; `complete` = dev said done; `closed` = QA passed |
| `stages` | Status of each stage, with timestamps, summary and artifact path |
| `cycle_history` | Archived stage results of earlier cycles (appended on each reopen after completion) |
| `effort` | **The raw interval log** – every timed interval (see §4) |
| `complexity` | Raw factor counts, weights, score, tier, day estimate |
| `sync` | Revision, last sync time, `dirty` flag, prompt counter |
| `anomalies` | Sync failures, drift, self-heal escalations, missing session ids |

Stage state (real sample – requirements approved, discovery waiting for you):

```json
"stages": {
  "requirements": { "status": "approved", "started_at": "2026-09-26T22:18:26Z",
                    "submitted_at": "2026-09-26T22:18:27Z", "approved_at": "2026-09-26T22:18:28Z",
                    "summary": "Scope agreed", "artifact": "docs/mda/4521/requirements.md" },
  "discovery":    { "status": "awaiting_approval", "summary": "12 paths",
                    "artifact": "docs/mda/4521/discovery.md" },
  "plan":         { "status": "not_started" }
}
```

Statuses: `not_started` → `in_progress` → `awaiting_approval` → `approved` (request changes sends it back to `in_progress` and bumps `revisions`).

---

## 4. The effort log (what efficiency is built from)

Each entry is one **bounded** interval. Effort is never "last event minus first event", so nights, meetings and days off are excluded automatically.

```json
{ "id": "fefda681b078", "session_id": "demo1", "cycle": 1,
  "stage": "requirements", "phase": "dev", "kind": "ai", "trigger": null,
  "start": "2026-09-21T14:13:20Z", "end": "2026-09-21T14:15:20Z",
  "seconds": 120.0, "raw_seconds": 120.0, "capped": false,
  "est_tokens": 4, "agent": "orchestrator", "slash_cmd": "/requirements" }
```

| Field | Notes |
|---|---|
| `kind` | `ai` = a turn (your prompt → agent stops). `approval` = your review time (approval minus last agent response). `manual` = logged manual QA minutes. `subagent` = timing breakdown only, **not added to totals** (it's already inside the `ai` turn) |
| `phase` | `dev`, `qa-authoring` (AI drafts scenarios), `qa-execution` (manual, no AI) – never blended |
| `trigger` | Why this work happened after a reopen: `pr-review`, `sonar-recheck`, `qa-defect`, `dev-reopen` |
| `seconds` vs `raw_seconds`, `capped` | Turns or approval gaps over 120 min are truncated (you probably walked away) and flagged. Report the count of capped intervals next to any total |
| `est_tokens` | Estimated from prompt length (chars ÷ 4). Hooks don't see model token counts |

Real result from the simulated story: AI turn 120 s + approval gap 540 s + discovery turn 200 s = **860 s active**; the 45 s sub-agent interval is not double-counted.

**Stage formula:** `active effort = Σ AI turn seconds + (approval time − last agent response time)`.
**Story total** = sum across every stage, session, day and cycle for that story ID. **Calendar duration** (first event → last event) is reported separately.

---

## 5. Complexity data

Stored raw, so the model can be recalibrated later:

```json
"complexity": { "result": {
  "model_version": "0.1-starting-weights", "calibrated": false,
  "counts":  { "screen_simple": 4, "complex_form": 2, "business_function": 12, "validation_rule": 10,
               "internal_api_endpoint": 3, "external_integration": 1, "db_object": 6, "test_scenario": 20 },
  "weights": { "screen_simple": 1, "complex_form": 3, "business_function": 0.5, "validation_rule": 0.25,
               "internal_api_endpoint": 1.5, "external_integration": 3, "db_object": 0.5, "test_scenario": 0.2 },
  "points_by_factor": { "screen_simple": 4, "complex_form": 6, "business_function": 6.0, "...": "..." },
  "score": 33.0, "tier": "High",
  "traditional_days": { "low": 6, "high": 10, "point": 8.0 },
  "efficiency_assumed": 0.3, "baseline_efficiency": 0.4, "expected_agentic_days": 5.6,
  "developer_adjustment": { "from_tier": "High", "to_tier": "Medium", "note": "…" }   // only if you changed it
} }
```

Legacy Analyst records the counts at `/discover`; the Target Architect scores at `/plan`; you confirm or adjust the tier at the Architecture gate. While `calibrated` is `false` every report carries an **UNCALIBRATED, internal use only** banner.

---

## 6. What lands in ADO

One work item per **(story, cycle, stage, phase)**, titled `MDA-4521-c1-requirements-dev`, tag `MDA-EffortRecord`, child of the story.

**The full record is always pushed as JSON.** No custom fields are required for data to land safely in ADO or for crash recovery — the agent tries the structured fields below first and, if they don't exist yet in your process, automatically falls back to writing the same JSON into the standard Description field (`ado check` / a failed field write never blocks a sync). Custom fields are only needed so ADO charts, queries and Power BI/Analytics can group and sum by an individual value (tier, developer, sprint...) instead of everything sitting inside one JSON blob. Create them ([ado-setup.md](ado-setup.md)) when you're ready to build dashboards, not before. If you do:

| Field | Example | Use |
|---|---|---|
| `Custom.MDAProject` / `MDAStoryId` / `MDACycle` | LAP-Civica / 4521 / 1 | Grouping |
| `MDAStage` / `MDAPhase` / `MDATrigger` | build / dev / sonar-recheck | Slice by stage, isolate QA execution, count rework by cause |
| `MDASprint` | Sprint 12 | Sprint views (sprint with most effort in that row) |
| `MDAActiveEffortHours` / `MDACalendarHours` | 1.6 / 30.2 | Effort vs elapsed |
| `MDATier` / `MDATraditionalDays` | High / 8 | Baseline for efficiency |
| `MDAFactors` / `MDAWeights` | JSON text | Recalibration |
| `MDADeveloper` | fujale-dev | Confirmed account |
| `MDATokens` | 1,240 | Estimated story tokens |
| `MDAPayload` | JSON | Full row detail |

Plus `MDA-4521-state` (the whole story JSON, used for recovery) and `MDA-usage-<login>-<date>` (developer's cumulative month-to-date Copilot premium requests, snapshotted at most daily).

---

## 7. The dashboard feed: `usage-metrics.ndjson`

One JSON line per **day + developer + story**, shaped like GitHub's Copilot usage-metrics user-level schema so both can share a report model (join on `day` + `user_login`). Real record (abbreviated):

```json
{ "day": "2026-09-21", "user_login": "fujale-dev",
  "user_initiated_interaction_count": 2,
  "used_cli": true, "used_agent": true,
  "totals_by_cli": { "prompt_count": 2, "request_count": 2, "session_count": 1,
                     "token_usage": { "prompt_tokens_sum": 6, "output_tokens_sum": null, "avg_tokens_per_request": 3.0 } },
  "totals_by_slash_cmd":   [ { "slash_cmd": "/discover", "interaction_count": 1 },
                             { "slash_cmd": "/requirements", "interaction_count": 1 } ],
  "totals_by_custom_agent":[ { "custom_agent": "legacy-analyst", "interaction_count": 1 } ],
  "totals_by_stage": [ { "cycle": 1, "stage": "requirements", "phase": "dev", "trigger": null,
                         "interaction_count": 1, "ai_seconds": 120.0, "approval_seconds": 540.0,
                         "manual_seconds": 0.0, "prompt_tokens_sum": 4 },
                       { "cycle": 1, "stage": "discovery", "phase": "dev", "ai_seconds": 200.0, "...": "..." } ],
  "loc_added_sum": null, "ai_credits_used": null, "user_id": null,
  "mda": { "schema": "mda-user-story-day/1", "project": "LAP-Civica", "story_id": "4521",
           "sprint": "Sprint 12", "active_seconds": 860.0,
           "active_seconds_by_phase": { "dev": 860.0, "qa-authoring": 0, "qa-execution": 0 },
           "capped_intervals": 0, "tokens_estimated": true,
           "complexity": { "tier": "High", "score": 33.0, "calibrated": false, "counts": { "...": "..." }, "weights": { "...": "..." } } } }
```

`null` means "not measurable from hooks", never zero. (In this simulation the sub-agent name shows as a generic value because the fake hook payload carried none; real hook payloads name the agent.)

---

## 8. Tracking efficiency

**Measured efficiency (dev phase, per story)**

```
traditional_hours   = traditional_days.point × hours_per_day (7.5)
measured_efficiency = 1 − (dev active hours ÷ traditional_hours)
```

Example: tier High → 8 days = 60 h traditional. Measured dev active effort 36 h → **40%** efficiency, against the tier's assumed 30% and the programme baseline of ~40%. `expected_agentic_days` (5.6) is the model's prediction; compare it with `dev active hours ÷ 7.5`.

Rules that keep the number honest:
1. **Only `phase = dev` counts toward the AI-efficiency claim.** QA authoring is tracked against its own baseline; QA manual execution is a separate line with no efficiency claim.
2. **Include rework.** Sum across all cycles for the story; `trigger` shows how much came from reviews, Sonar and QA defects.
3. **Traditional days is itself an estimate** from a model that is uncalibrated. Until you calibrate against real completed stories, efficiency figures are internal indicators, not results. After calibration, prefer comparing against actual historical effort.
4. The ~40% baseline is an anchor assumption; the remaining ~60% (approvals, review, PR, manual QA, Sonar triage) is manual by design and appears as `approval` and `manual` time.
5. Watch `capped_intervals`: many capped turns means the timer overstates active work.

**Useful questions the data answers**

| Question | Slice |
|---|---|
| Are we hitting ~40%? By tier? | Efficiency by `tier`; expect the gain to narrow as tier rises |
| Where does time go? | `totals_by_stage`: AI vs approval time per stage |
| How much rework? | Effort where `trigger` is not null, ÷ total |
| Which factor drives cost? | Regress hours on `counts` (this is what calibration does) |
| Who/what is consuming Copilot quota? | `MDA-usage-*` rows by `MDADeveloper` and date (developer-level, not story-level) |
| Sprint load | Effort by `MDASprint`, dev vs QA phases |

---

## 9. Building the dashboard

### Option A: native ADO dashboard (start here)

Work item query (Chart for Work Items widgets, grouped by a field, summing `MDAActiveEffortHours`):

```
Select [System.Id], [System.Title] From WorkItems
Where [System.Tags] Contains 'MDA-EffortRecord'
  And [Custom.MDAProject] = 'LAP-Civica'
  And [Custom.MDAPhase] <> 'qa-execution'
```

Tiles: effort by developer, by tier, by sprint, by stage; tokens by developer; a separate QA-execution tile; count of records with a `MDATrigger` (rework). One dashboard per project. Native widgets can't give a project dropdown or a date picker.

### Option B: Power BI (interactive filters)

Connect to Analytics OData: `https://analytics.dev.azure.com/<org>/<project>/_odata/v4.0-preview/WorkItems?$filter=contains(Tags,'MDA-EffortRecord')&$select=WorkItemId,Title,Custom_MDAProject,Custom_MDAStoryId,Custom_MDACycle,Custom_MDAStage,Custom_MDAPhase,Custom_MDATrigger,Custom_MDATier,Custom_MDATraditionalDays,Custom_MDAActiveEffortHours,Custom_MDADeveloper,Custom_MDASprint`. Check field exposure first: `mda.py ado analytics`. Example measures:

```
Dev Hours   = CALCULATE(SUM(Effort[Custom_MDAActiveEffortHours]), Effort[Custom_MDAPhase] = "dev")
Trad Hours  = SUMX(DISTINCT(Effort[Custom_MDAStoryId]), CALCULATE(MAX(Effort[Custom_MDATraditionalDays])) * 7.5)
Efficiency  = 1 - DIVIDE([Dev Hours], [Trad Hours])
Rework %    = DIVIDE(CALCULATE([Dev Hours], NOT ISBLANK(Effort[Custom_MDATrigger])), [Dev Hours])
```

Add a slicer each for project, developer, sprint and a date table for the range. Requires Power BI Pro and Analytics enabled.

### Option C: files (no ADO fields needed)

Load the NDJSON, or `.mda/stories/*.json`, directly:

```python
import pandas as pd, json, glob
rows = [json.loads(l) for f in glob.glob("docs/mda/*/usage-metrics.ndjson") for l in open(f)]
df = pd.json_normalize(rows, sep=".")
by_stage = pd.json_normalize(rows, record_path="totals_by_stage", meta=["day", "user_login", ["mda", "story_id"]], sep=".")
print(by_stage.groupby("stage")[["ai_seconds", "approval_seconds"]].sum() / 3600)
```

### Option D: the pipeline

`mda-effort-export` (manual run) writes an Excel workbook (Effort Rows, Story Summary, QA Manual Execution, Developer Usage) as a build artifact and **appends** a Wiki entry with the link. The link requires ADO sign-in with project access, and the pipeline identity needs Wiki edit permission.

---

## 10. Limits to keep in mind

- Live ADO, the Wiki write, the usage endpoint and the exact Copilot hook payloads have not been exercised end to end; run a pilot story first and compare a report against your own stopwatch.
- Token figures are estimates; developer premium-request usage is cumulative month-to-date (daily deltas approximate).
- Complexity numbers are uncalibrated. Keep them out of client-facing material until calibration is accepted.
- Effort caps (120 min) and the self-heal retry cap (3) are placeholders awaiting a governance decision.
