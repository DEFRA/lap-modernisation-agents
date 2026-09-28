# ADO setup for the Migration Delivery Agent

**None of this section is required to start using the agent.** Every record is pushed to ADO as full JSON regardless: with these fields it also populates individual queryable columns; without them, the agent detects the missing fields and writes the same JSON into the work item's Description instead, automatically, with no manual step and no data loss. Only do this once you want native ADO charts, Analytics or Power BI to group/sum by tier, developer, sprint, stage, etc. — see [dashboards.md](dashboards.md).

## 1. Work item type and fields (optional — for dashboards)
Use an existing type (default `Task`, config `ado.effort_record_type`) or create a custom **Effort Record** type in an inherited process. Add these fields (reference names are configurable in `mda.config.json` → `ado.fields`):

| Key | Reference name | Type |
|---|---|---|
| key | Custom.MDARecordKey | Text (single line) |
| project | Custom.MDAProject | Text |
| story_id | Custom.MDAStoryId | Integer |
| sprint | Custom.MDASprint | Text |
| cycle | Custom.MDACycle | Integer |
| stage | Custom.MDAStage | Text |
| phase | Custom.MDAPhase | Text (dev / qa-authoring / qa-execution) |
| trigger | Custom.MDATrigger | Text |
| factors | Custom.MDAFactors | Text (multi-line, JSON raw counts) |
| weights | Custom.MDAWeights | Text (multi-line, JSON weights applied) |
| tier | Custom.MDATier | Text |
| traditional_days | Custom.MDATraditionalDays | Decimal |
| effort_hours | Custom.MDAActiveEffortHours | Decimal |
| calendar_hours | Custom.MDACalendarHours | Decimal |
| developer | Custom.MDADeveloper | Text (confirmed account) |
| tokens | Custom.MDATokens | Integer |
| recorded_at | Custom.MDARecordedAt | Date/time |
| payload | Custom.MDAPayload | Text (multi-line / HTML, full JSON) |

Add the fields to the type's layout, or the API rejects them. If they are missing the agent falls back to payload-only records (in `System.Description`) and logs nothing louder — run `mda.py ado check` after setup.

## 2. Analytics
Confirm the fields are exposed to Analytics/OData: `python .github/scripts/mda.py ado analytics` (`Custom_MDA*` names). New fields can take some time to appear. Dashboards and Power BI depend on this.

## 3. PAT
Scopes: Work Items (read & write), Wiki (read & write), Analytics (read). Expiry cannot be read from the PAT, so export `MDA_ADO_PAT_EXPIRY`. Expired ⇒ blocked; ≤ 7 days ⇒ warning, re-checked at next session start. Wiki-write scope cannot be probed non-destructively; it is confirmed on the first wiki append.

## 4. Export pipeline permissions
The pipeline in `.github/pipelines/mda-effort-export.yml` runs as the Project Build Service identity. Grant it **Wiki edit** (a separate grant from work-item/Analytics read). The artifact link in the Wiki requires ADO sign-in with project access; it is not a public download.

## 5. Sprints
List sprint start/end dates in `.mda/config.local.json` → `sprints` so effort can be bucketed and split across sprint boundaries.
