---
name: migration-delivery-discovery
description: Rules for counting the complexity factors of a migration user story from the legacy code. The counts drive the complexity tier and are the evidence for the traditional-effort estimate, so every count must be backed by evidence.
---

# Discovery: counting the factors

The counts you record are weighted by the complexity model to give the tier, and they are the evidence the Target Architect uses to estimate the traditional effort. A wrong count moves both. Count what this story must migrate, not the whole application.

## Rules for every factor
- Count only items **in this story's scope** (traced from the approved requirements), found in `paths.old`.
- Each count must list its evidence in `discovery.md`: `factor: N` followed by file path and symbol for each counted item. A count with no listed evidence is not allowed.
- When unsure, record your best count and the ambiguity under "Open questions"; the developer can adjust at the gate. Never round up to be safe and never copy a number from another story.
- Count each distinct item once, even if several screens reuse it.

## Factors

| Factor | One unit is |
|---|---|
| `screen_simple` | A page/view with display or a few inputs, no multi-step logic or conditional sections |
| `complex_form` | A form with multi-step flow, conditional sections, dependent controls, or more than ~15 fields |
| `business_function` | A method/class holding business rules (not plumbing, not a property getter) that must be re-implemented |
| `validation_rule` | A distinct validation (server or client) with its own message/condition |
| `internal_api_endpoint` | An endpoint/handler this application exposes to its own front end or other internal callers |
| `external_integration` | A call to, or from, a system outside the application (third-party API, queue, file drop, email gateway) |
| `db_object` | A table, view or type touched by the story |
| `stored_procedure` | A stored procedure or function the story calls or must port |
| `ssis_package` | An SSIS package or ADF pipeline the story depends on |
| `wcf_asmx_service` | One WCF/ASMX service **operation** to be converted (count operations, not service classes) |
| `report_template` | A report/PDF template (SSRS, Crystal, bespoke) the story produces or changes |
| `background_job` | A scheduled job, Windows service, or hosted worker the story touches |
| `identity_flow` | A distinct authentication/authorisation flow (login, SSO, role mapping, token handling) |
| `test_scenario` | A distinct behaviour that needs a test (the Target Architect refines this at /plan) |

If you meet something that fits none of these but clearly costs effort (for example a bespoke PDF engine or a COM interop layer), do **not** shoehorn it into a factor. Record it under "Uncounted effort" with a one-line reason and a rough size in days; the Target Architect includes it in the traditional estimate with its reason.

## Recording
`python .github/scripts/mda.py complexity counts --json '{"screen_simple":N, ... all factors you counted ...}'` (factors you leave out are stored as 0). Do not score or estimate here.
