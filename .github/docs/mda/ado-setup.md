# ADO setup for the Migration Delivery Agent

## Do you need work items at all?

**The agent needs a place in ADO to keep its records, and a work item is the cheapest one that works for every team.** Nothing else is required: no extra infrastructure, the PAT you already need, per-project permissions and history for free, records linked to the user story, and queryable by WIQL, Analytics and Power BI.

Alternatives and why they lose: a committed JSON file in the repo (merge conflicts between developers, no per-project permissions); Azure Storage/Table (new infrastructure, new credentials, outside the boards); Azure Artifacts (not queryable). The pipeline and the agent read and write through one small client, so the store could be swapped later, but nothing here recommends it.

What *is* optional is the custom **fields**. The agent always writes the full JSON record into one long-text field. The pipeline reads that JSON, so **the Excel report works with only `Custom.MDAPayload`** (or, if even that is missing, the agent falls back to the work item's Description automatically). The other fields exist so ADO charts, queries and Power BI can group and filter without parsing JSON.

## Where to create them

- **In the same ADO project as the user story**, one set per team. Two teams on two projects means each project holds its own records; a story's records always go to the project chosen at `/setup`. Records are **child work items of the user story** (the agent adds the parent link), so they appear under the story and never at the top of a backlog.
- **Recommended type: a custom work item type "MDA Effort Record"** in an inherited process (Organization settings > Process > create an inherited process from the one your project uses > New work item type). A custom type does not appear on boards or backlogs unless you add it to a backlog level, so it does not clutter the team's board. Set `ado.effort_record_type` to its name.
- **Fallback with no admin rights: `Task`** (the default). Records are tagged `MDA-EffortRecord`. To keep them off the board, add the tag as a board card style / exclude it with a backlog query, or just filter the board by tag.
- Creating the type and fields needs an **Edit process** permission (usually Project Collection Administrator). It is a one-off per process; teams on the same process share it.
- Config for two projects, in `.mda/config.local.json` or the committed `mda.config.json`:

```json
{ "ado": {
    "org_url": "https://dev.azure.com/<org>",
    "effort_record_type": "MDA Effort Record",
    "projects": [
      { "name": "Team A Project", "team": "Team A", "wiki_id": "" },
      { "name": "Team B Project", "org_url": "https://dev.azure.com/<other-org>", "team": "Team B" }
    ] } }
```
With `projects` set, `/setup` rejects any project not in the list, and each entry can override the org URL and wiki.

## Records written (all tagged `MDA-EffortRecord`)

| Title | Record type | Written by | Grain |
|---|---|---|---|
| `MDA-<story>-<developer>-<yyyy-mm-dd>-c<cycle>-<stage>` | `effort` | the developer's own machine | one per developer, work date, cycle, stage: hours (AI / approval / manual), tokens in/out/estimate, token source; payload adds agents, models, sessions |
| `MDA-<story>-estimate` | `estimate` | at plan / `estimate confirm` | the traditional estimate (PD per phase, each with its reason and source, who confirmed), tier, complexity counts, application and technology stack |
| `MDA-<story>-state-<developer>` | `state` | each developer | recovery snapshot; recovery merges all developers' snapshots by entry id |
| `MDA-usage-<login>-<date>` | `usage` | `mda.py usage` | developer premium-request snapshot (billing, not tokens) |

Because the key contains the developer and the date, two developers on one story never overwrite each other, and any date range is answered exactly.

## Fields

Reference names are configurable in `mda.config.json` > `ado.fields`. Add them to the work item type's layout, or the API rejects them.

| Key | Reference name | Type | Needed for |
|---|---|---|---|
| payload | `Custom.MDAPayload` | Text (multi-line), **plain text** | **Required by the pipeline** (full JSON; up to about 1 MB; if you choose the HTML flavour, still fine, but plain text avoids escaping) |
| key | `Custom.MDARecordKey` | Text (single line) | optional |
| record_type | `Custom.MDARecordType` | Text: effort / estimate / state / usage | filtering |
| project | `Custom.MDAProject` | Text | filtering |
| story_id | `Custom.MDAStoryId` | Integer | filtering, grouping |
| developer | `Custom.MDADeveloper` | Text | effort by developer |
| work_date | `Custom.MDAWorkDate` | Date | **date-range queries and charts** |
| sprint | `Custom.MDASprint` | Text | sprint grouping |
| cycle | `Custom.MDACycle` | Integer | optional |
| stage | `Custom.MDAStage` | Text | grouping |
| phase | `Custom.MDAPhase` | Text (dev / qa-authoring / qa-execution / transition_to_live / support / unassigned) | grouping |
| trigger | `Custom.MDATrigger` | Text | optional |
| ai_hours | `Custom.MDAAiHours` | Decimal | automated completion |
| approval_hours | `Custom.MDAApprovalHours` | Decimal | optional |
| manual_hours | `Custom.MDAManualHours` | Decimal | optional |
| effort_hours | `Custom.MDAActiveEffortHours` | Decimal | effort sums |
| tokens_in | `Custom.MDATokensIn` | Integer | real input tokens (OpenTelemetry) |
| tokens_out | `Custom.MDATokensOut` | Integer | real output tokens |
| tokens_est | `Custom.MDATokensEst` | Integer | prompt-size estimate only; never added to the real figures |
| token_source | `Custom.MDATokenSource` | Text: otel / estimate / none | data quality |
| tier | `Custom.MDATier` | Text | estimate record |
| traditional_pd | `Custom.MDATraditionalPD` | Decimal | estimate record (total PD) |
| recorded_at | `Custom.MDARecordedAt` | Date/time | optional |

The minimum useful set if you want to keep it small: **payload, record_type, project, story_id, developer, work_date, stage, effort_hours, tokens_in, tokens_out**. Run `python .github/scripts/mda.py ado check` after setup (it also probes every PAT scope).

If a field is missing the agent detects the rejected write and stores the same JSON in `System.Description` instead (`structured: false`), with no data loss. Only that exact error ("TF51535 / does not exist / Cannot find field") triggers the fallback; other 400s are real errors.

## Volume

One effort record per developer, per working day, per stage touched: a story that takes two developers a week produces tens of records, not thousands. Rows are rewritten only when their content changed. Token usage is rolled up to one entry per turn per agent before sync, so the state snapshot stays well under the field limit.

## Analytics
Confirm the fields are exposed to Analytics/OData: `python .github/scripts/mda.py ado analytics` (`Custom_MDA*` names). New fields can take some time to appear. Dashboards and Power BI depend on this; the Excel pipeline does not.

## PAT
Scopes: Work Items (read & write), Wiki (read & write, only if you append to the wiki), Analytics (read). Expiry cannot be read from the PAT, so export `MDA_ADO_PAT_EXPIRY`. Expired = blocked; 7 days or less = warning. A developer on Team B needs a PAT for Team B's organisation/project.

## Pipelines
Create **one pipeline per ADO project** from `.github/pipelines/mda-ai-efficiency-report.yml`. The Project Build Service identity needs Work items: read. Add **Wiki edit** only if you tick "append to wiki". The artifact (the .xlsx) requires ADO sign-in with project access; it is not a public link.

## Developer attribution
Each entry carries the developer that was confirmed on that machine (`setup confirm-account`). When a second developer works the same story, their entries keep their login and sync under their own keys; the local account is never replaced by someone else's when data is merged.

## Sprints
List sprint start/end dates in `.mda/config.local.json` > `sprints` so effort can be bucketed and split across sprint boundaries.
