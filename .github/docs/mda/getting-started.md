# Getting started: from nothing to your first AI Efficiency Excel

Everything in order. Parts A and B are one-off; Part C is what you do per story; Part D is how the report comes out.

```
 Developer (VS Code Copilot Chat or Copilot CLI)
   |  /setup, /requirements, /discover, /plan, /build ...      <- you type commands, you approve each stage
   v
 .mda/ on your machine  (story cache + Copilot OpenTelemetry file = real tokens)
   |  syncs automatically at every gate, on a heartbeat, and at session end
   v
 Azure DevOps project   (work items: one record per developer / day / stage, one estimate per story)
   |  you run the pipeline when you want a report (it runs INSIDE Azure DevOps)
   v
 AI Efficiency Excel    (pipeline artifact, any date range, all developers)
```

Who does what: **Part A = a team lead / ADO admin, once per ADO project. Part B = every developer, once per machine. Part C = developers, per story. Part D = anyone who can run the pipeline.**

---

## Part A: Azure DevOps (once per ADO project)

### A1. Decide where the records live: a work item type
The agent stores its records as ADO work items, in the **same project as the user story**, linked to it. You do **not** create a work item per story: the agent creates and updates them itself. You only prepare *the type they use*, once. Pick one:

| Option | Admin rights | Effect |
|---|---|---|
| **Fastest start: keep `Task`** (the default) | none | Works immediately. Records are Tasks tagged `MDA-EffortRecord`, data kept as JSON in the Description (no queryable columns). They can show up as child tasks under the story on sprint boards. The Excel pipeline works either way. |
| **Recommended: a custom type "MDA Effort Record"** | Edit-process permission | Clean: not shown on boards, queryable columns for dashboards. One-off setup below. |

You can start with Task and upgrade later; old records stay readable.

### A2. (Recommended) Create the custom type and fields
1. **Organization settings > Boards > Process.** Find the process your project uses (for example *Agile*). If it is a built-in (system) process, open its **...** menu > **Create inherited process** and name it, for example `Agile - MDA`. Then on the new process, **Projects** tab > **...** next to your project > **Change process** > select the inherited process.
2. Open the inherited process > **Work item types** > **New work item type**. Name: `MDA Effort Record`. Choose any icon and colour > **Create**.
3. Open the new type > **Layout** > **New field** (add each field below from the Layout page, so it is placed on the form). **The field name decides the reference name**: ADO builds `Custom.<name without spaces>`, so type the names exactly as below.

   | Field name (type exactly) | Type | Required by |
   |---|---|---|
   | `MDAPayload` | Text (multiple lines), plain text | **the pipeline reads this** |
   | `MDARecordType` | Text (single line) | filtering |
   | `MDAProject` | Text (single line) | filtering |
   | `MDAStoryId` | Integer | grouping |
   | `MDADeveloper` | Text (single line) | by developer |
   | `MDAWorkDate` | Date/Time | **date-range queries** |
   | `MDAStage` | Text (single line) | grouping |
   | `MDAPhase` | Text (single line) | grouping |
   | `MDAActiveEffortHours` | Decimal | sums |
   | `MDATokensIn` | Integer | real input tokens |
   | `MDATokensOut` | Integer | real output tokens |

   Optional extras (the full list is in [ado-setup.md](ado-setup.md)): `MDARecordKey`, `MDASprint`, `MDACycle`, `MDATrigger`, `MDAAiHours`, `MDAApprovalHours`, `MDAManualHours`, `MDATokensEst`, `MDATokenSource`, `MDATier`, `MDATraditionalPD`, `MDARecordedAt`. Any field you do not create is simply skipped.
4. Tell the agent the type name. In `.github/config/mda/mda.config.json` (committed, shared by the team) set `"effort_record_type": "MDA Effort Record"`.
5. **Prove it** (after Part B step B3): `python .github/scripts/mda.py ado selftest --project "<ADO project>"`. It creates a test record with every field, reads it back, deletes it, and says either *"Work item type and every custom field accepted"* or *"custom fields were rejected, data stored as JSON in the Description"* (still works; fix the field names).

### A3. Two teams, two ADO projects
Repeat A1-A2 in each project. Tell the agent which projects exist, in `.github/config/mda/mda.config.json` (or each developer's `.mda/config.local.json`):

```json
{ "ado": { "org_url": "https://dev.azure.com/<org>",
           "projects": [ { "name": "Team A Project" }, { "name": "Team B Project" } ] } }
```
`/setup` then only accepts those names, and a story's records go to the project chosen there. PATs belong to an **organisation**: if the two projects are in different organisations, add `"org_url"` to the entry, and a developer works in one organisation at a time.

### A4. Create the reporting pipeline (runs in Azure DevOps)
Yes: the Excel is produced **inside Azure DevOps** by a pipeline (a Microsoft-hosted Linux agent installs `openpyxl`, reads every developer's records from your project via the REST API, and publishes the `.xlsx` as a build artifact). No developer machine is involved. The pipeline definition is the file `.github/pipelines/mda-ai-efficiency-report.yml` in this repository; ADO needs to be able to read that repository.

Do this **in each ADO project** that has records:
1. **Pipelines > New pipeline.**
2. Where is your code: **GitHub** (first time: authorise the *Azure Pipelines* GitHub app and select the repository) or **Azure Repos Git** (select the repo).
3. **Configure:** *Existing Azure Pipelines YAML file* > branch (for example `main`) > path **`/.github/pipelines/mda-ai-efficiency-report.yml`** > **Continue**.
4. On the review page open the **Run** drop-down and choose **Save** (do not run yet). Rename it (**Pipelines > ... > Rename**) to `MDA AI Efficiency Report`.
5. Permissions. The pipeline runs as **`<Project> Build Service (<org>)`**. It normally already has read access to the project's work items. If a run fails with 401/403 or TF401019, grant that identity *View work items in this node* on the project's area path (**Project settings > Project configuration > Areas > Security**). Wiki edit is needed only if you tick *append to wiki* (**Repos/Wiki > Security**).
6. If the first run says there is no hosted parallelism, request the free Microsoft-hosted grant for the organisation (or use a self-hosted agent).

The pipeline needs no secrets and no organisation URL: it uses the running project and the built-in `System.AccessToken`.

---

## Part B: each developer's machine (once)

### B1. Install
- Python 3.9+, `git`, GitHub CLI (`winget install --id GitHub.cli` on Windows, `brew install gh` on macOS) and `gh auth login`.
- VS Code with GitHub Copilot Chat (the usual runtime), and/or the Copilot CLI.

### B2. Get the agent into your workspace
The agents, prompts, hooks and scripts all live under `.github/` of the repository you open. Either open this repository as the workspace, or copy its `.github/` folders (`agents`, `prompts`, `skills`, `hooks`, `lib`, `scripts`, `config`) into your migration repository. **Put the legacy (old) and new codebases in the same workspace** (VS Code: *File > Add Folder to Workspace*) so Copilot can read them; `/setup` asks for their paths.

### B3. Your Azure DevOps token and connection
1. Azure DevOps > user settings (top right) > **Personal access tokens** > **New token**. Organisation: yours. Scopes (custom): **Work Items: Read & write**, **Wiki: Read & write** (only if you will append to the wiki), **Analytics: Read**. Note the expiry date; copy the token now (shown once).
2. Set environment variables, then **open a fresh terminal / restart VS Code**:

   | Variable | Value |
   |---|---|
   | `MDA_ADO_PAT` | the token |
   | `MDA_ADO_PAT_EXPIRY` | `YYYY-MM-DD` (ADO cannot tell us the expiry) |
   | `MDA_ADO_ORG_URL` | `https://dev.azure.com/<org>` |
   | `MDA_ADO_PROJECT` | **only if you work in one project**; leave unset if you switch between the two (it would force every story into that project) |

   Windows (current user, persistent): `setx MDA_ADO_PAT "<token>"` (and the others). macOS: add `export MDA_ADO_PAT="<token>"` to `~/.zshrc`, then `source ~/.zshrc` (or keep the token in the Keychain). Never commit these.

### B4. Turn on real token capture (Copilot OpenTelemetry)
In the workspace `.vscode/settings.json`:

```json
{
  "github.copilot.chat.otel.enabled": true,
  "github.copilot.chat.otel.exporterType": "file",
  "github.copilot.chat.otel.outfile": "${workspaceFolder}/.mda/otel/copilot.jsonl",
  "github.copilot.chat.otel.captureContent": false
}
```
For the Copilot CLI: set `COPILOT_OTEL_ENABLED=true` and `COPILOT_OTEL_FILE_EXPORTER_PATH=<repo>/.mda/otel/copilot.jsonl`. `captureContent` stays false, so no prompts or code are written. Details and caveats: [otel-setup.md](otel-setup.md). Run one chat message, then: `python .github/scripts/mda.py otel check`. **It must say `"ok": true` with token totals before you trust any token figure.**

### B5. Optional local config
`.mda/config.local.json` (git-ignored): sprint dates so effort is split by sprint, and the project list if you do not want to commit it:

```json
{ "sprints": [ { "name": "Sprint 12", "start": "2026-09-01", "end": "2026-09-14" } ] }
```

### B6. Check everything
```
python .github/scripts/mda.py doctor          # python, git, gh, hooks, PAT, org, scopes, telemetry
python .github/scripts/mda.py ado selftest --project "<ADO project>"   # proves the work item type and fields (creates then deletes a test record)
```
Fix every `fail`; read every `warn`. (`doctor` exits 3 while anything fails.)

### B7. Start the agent
- **VS Code Copilot Chat:** open Chat, pick the agent **migration-delivery** from the agent drop-down. There are no hooks in this mode, so the agent times turns itself and records your approval by re-checking the exact words you type (see [runtimes.md](runtimes.md)).
- **Copilot CLI:** run `copilot` in the repository and select `migration-delivery`. Hooks in `.github/hooks/mda-hooks.json` time turns and record approvals independently of the model. *Not yet verified on a real install: confirm in the pilot (Part E).*

---

## Part C: working a story (every command)

Type these in Copilot Chat. The agent runs the `python .github/scripts/mda.py ...` commands for you; you only need them to inspect things (cheat sheet below).

### C1. Start
| You type | What happens |
|---|---|
| `/setup 101` | Asks, one question at a time: ADO project (must be a configured one), story ID, is it a migration, **legacy (old) path**, new path, HLD / HLSA / LLD paths, **application name**, **technology stack**, which GitHub account to attribute to, auto-continue yes/no. Checks PAT and telemetry. Nothing else runs until this is complete. |
| `/resume-story 101` | Next day or new machine: reloads the story (from `.mda/` or, if missing, rebuilt from ADO). Never re-asks what is captured. |
| `/story-status` | Stages, which gate is waiting, cycle, last sync. Changes nothing. |

### C2. The pipeline: each stage ends at an approval gate
| You type | Stage and agent | You then |
|---|---|---|
| `/requirements 101` | requirements (reads the ADO story) | review, then reply **`approve`** or **`request changes: <what>`** |
| `/discover` | discovery (`legacy-analyst`): traces the legacy code, **counts complexity factors with evidence** | same |
| `/plan` | design, test plan, **complexity tier**, and the **traditional-effort estimate**: person-days per phase, a reason each, proposed by the LLM | check the table; change a phase with `/estimate`; **`approve`** only when happy |
| `/build` | build (`build-engineer`), delegating to the specialist migration agents | same |
| `/quality-check` | quality gates (build, tests, Sonar, security) with a retry cap | same |
| `/package-pr` | commit message, PR description | **you push and open the PR** (the agent never does) |

Approval is **only** your own reply `approve` / `request changes: ...`. "Looks fine" is rejected on purpose; the agent can never approve for you. With auto-continue ON the next stage starts right after you approve; it still stops at every gate.

After the PR: tell the agent the PR URL (`mda.py story pr-raised`), then answer *"is the story complete from a dev perspective?"*.

### C3. Work with no gate of its own (time is booked to the right stage)
`/research <question>` (to Discovery) · `/db-analysis` (Discovery, assessment only) · `/unit-test` (Test) · `/security-review` (Test) · `/document` (Design). Findings go to `docs/mda/<story>/`. They never advance a stage.

### C4. The estimate and manual effort
| You type | Use |
|---|---|
| `/estimate` | Show the traditional estimate; change a phase (a reason is mandatory); **confirm** it. Confirming means "I accept this as the baseline", not "this is measured". |
| `/log-manual` | Minutes spent on **Transition to Live** or **Support** (the agent does not run those), with a note; optionally your traditional figure for that phase. |
| `/qa-author` | QA test-case drafting (QA approves). |
| `/qa-log-execution` | Manual QA execution minutes, then the outcome (`pass` closes the story; `reopen` starts a new cycle). Shown as its own line, no AI-efficiency claim. |

### C5. After the PR, and on rework
`/fix-review` (PR comments) · `/fix-sonar` (Sonar findings) · `/reopen` (developer decision, QA defect) — each re-enters Build then Quality as a new commit on the same PR. Only you start these.

### C6. Reports and usage
| You type | Result |
|---|---|
| `/generate-report` | The story's effort/token/estimate report, `docs/mda/<story>/report.md` (+ `--wiki` on request). |
| `/benefits-report <project> [from] [to]` | **Local preview** of the AI Efficiency report from stories on this machine, with an `.xlsx`. |
| `/usage` | Your GitHub Copilot premium-request snapshot (billing, not tokens). |

### Command cheat sheet (you rarely type these)
```
python .github/scripts/mda.py session                 # which story is bound, hooked yes/no
python .github/scripts/mda.py setup status            # what is still missing
python .github/scripts/mda.py story status            # stages and gate
python .github/scripts/mda.py estimate show           # the traditional estimate
python .github/scripts/mda.py estimate set --phase build --pd 10 --reason "..." --source developer
python .github/scripts/mda.py estimate confirm
python .github/scripts/mda.py manual log --phase transition_to_live --minutes 90 --note "cutover"
python .github/scripts/mda.py otel check              # is token data arriving?
python .github/scripts/mda.py sync push               # force a sync to ADO now
python .github/scripts/mda.py report --print
python .github/scripts/mda.py benefits --project "Team A Project" --from 2026-09-01 --to 2026-09-30 --xlsx
python .github/scripts/mda.py doctor
```
There is deliberately **no command that approves a gate**.

---

## Part D: the Excel report

### D1. The real report (all developers, from ADO)
1. In the ADO project: **Pipelines > MDA AI Efficiency Report > Run pipeline**.
2. Fill the parameters:

   | Parameter | Meaning |
   |---|---|
   | From date / To date | `YYYY-MM-DD`, inclusive. **Leave both blank for all data.** From after To is rejected. Dates are work dates (the day the work happened). |
   | Story IDs | optional comma list; blank = all stories |
   | Application / Technology stack | optional header overrides; blank = taken from what developers entered at `/setup` |
   | Append to wiki | off by default |
3. **Run.** When finished, open the run > **Published > ai-efficiency-report** > download `ai-efficiency-<project>-<from>_<to>.xlsx`.
4. Run it once per ADO project; each reads only its own project.

### D2. Reading it
Sheet 1 mirrors the programme template: Application Context, Benefits (Effort saving, Time saving, Cost saving left blank, Automated completion) and the Delivery Comparison by phase with totals and percentages as live formulas. **Sheet 2 "Details"** lists the date range, stories, **data-quality flags** (read these first), tokens in/out by stage and by agent, and stories excluded because a phase had no traditional figure. Sheet 3 holds the raw rows. How each number is built: [benefits-report.md](benefits-report.md).

### D3. A preview without the pipeline
`python .github/scripts/mda.py benefits --project "<ADO project>" --xlsx` (add `--from`/`--to`) builds the same workbook from this machine's cached stories only; it understates the total if anyone else worked the project. `python .github/scripts/pipeline/demo_ai_efficiency.py` builds one from synthetic data to review the layout.

---

## Part E: is it ready? Verify before you rely on it

The logic is covered by 84 tests and a scripted end-to-end run of the whole local flow. Four things can only be proven on your systems, so **run one pilot story** and check:

1. `doctor` and `ado selftest` are clean; `otel check` shows real tokens after a Chat turn. *(If `otel check` finds no chat spans, send the first two lines of the file; the reader tolerates three common formats but the exact one was not observable here.)*
2. A pilot story reaches `approve` in your runtime. In Copilot CLI, confirm the hooks fire (`mda.py session` shows `hooked: true`).
3. After the story: `mda.py sync push` succeeds, and the records appear in ADO (query tag `MDA-EffortRecord`).
4. Run the pipeline once on the pilot data. Compare the effort hours with your own stopwatch for the day, and open the Excel to confirm the formulas show the same percentages as the markdown summary (`mda.py benefits ... --print`).

Standing limits: the **traditional effort is an LLM estimate** (labelled so everywhere); the complexity tier model is uncalibrated; tool-permission waits count as AI time; premium-request billing is a separate figure; Transition to Live and Support exist only through your manual entries.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `ado_not_configured` | `MDA_ADO_PAT` / `MDA_ADO_ORG_URL` missing in *this* terminal; open a fresh one after `setx` |
| `unknown_ado_project` at `/setup` | name not in `ado.projects`; the error lists the allowed names |
| `ado selftest` says fields rejected | field names do not match exactly (`Custom.MDA...`), or not added via the type's Layout |
| `otel check` file_missing / no chat spans | settings not applied (reload VS Code), org policy blocks the exporter, or a different path |
| Tokens show UNAVAILABLE in the report | telemetry was off for those turns; the report says so and counts rows by source |
| Approve not accepted | the reply must be exactly `approve` or `request changes: <text>` |
| Pipeline: 401/403 / TF401019 | grant `<Project> Build Service` work-item read on the area path |
| Pipeline: no hosted parallelism | request the free grant for the organisation, or use a self-hosted agent |
| Excel has blanks marked NEEDS INPUT | that phase has no traditional estimate; set it with `/estimate` or `/log-manual` |
| Report says `hooked: false` in Copilot CLI | the hooks file was not picked up; check `.github/hooks/mda-hooks.json` and the CLI version |

## Where to read more
[how-it-works-and-data-guide.md](how-it-works-and-data-guide.md) (data model) · [ado-setup.md](ado-setup.md) (fields, record types) · [otel-setup.md](otel-setup.md) · [benefits-report.md](benefits-report.md) · [runtimes.md](runtimes.md) (CLI vs VS Code) · [calibration.md](calibration.md) · [reuse-check.md](reuse-check.md).
