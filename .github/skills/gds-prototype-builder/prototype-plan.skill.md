# Skill: prototype-plan

## Purpose
Turn either the legacy UI inventory or the developer's prompts into a concrete, phased,
page-by-page plan — the thing `prototype-scaffold-and-build` actually builds from. No page gets
built without first appearing in this plan.

## Trigger Conditions
- Runs after `intake-and-setup`, and after `legacy-ui-discovery` when a legacy source was given.
- Takes `legacy-ui-inventory.json` (legacy source) or `prompts` (greenfield source) as its input.

---

## Step 1 — Choose the Planning Mode

| Source | Mode |
|---|---|
| `referenceProjectPath` was given | **Migration mode** — plan from `legacy-ui-inventory.json` |
| `prompts` was given | **Greenfield mode** — plan from the developer's free-text description |

---

## Step 2A — Migration Mode: Map Every Legacy Page to a GDS Pattern

For every page in `legacy-ui-inventory.json`, choose the closest Design System component or
pattern — reuse the same mappings the `gds-ui` agent applies to real code:

| Legacy shape | GDS pattern |
|---|---|
| Multi-field form on one page | One question per page (govuk question-pages pattern) |
| Data grid / table | `govuk-table`, with `govuk-tag` for any status column |
| Dropdown/select with few options | `govuk-radios` |
| Dropdown/select with many options | `govuk-select` or an autocomplete pattern |
| Free-text confirmation panel | `govuk-panel` (confirmation page) |
| Inline validation message | `govuk-error-message` + `govuk-error-summary` |
| Custom dashboard widget / bespoke chart | No direct equivalent — flag as an **open item**, propose the closest existing pattern, do not invent bespoke UI |

Where a single legacy page becomes several GDS question pages (the common case — legacy multi-field
forms almost always split), record the mapping as one-to-many and preserve the original page's
position in the journey as the position of the *first* new page in that group.

## Step 2B — Greenfield Mode: Structure the Prompts into Pages and Journeys

From `prompts`, extract:
- A list of pages, in the order the developer described.
- What each page asks or shows.
- Any branching described ("if X, skip to Y").

If the prompt is ambiguous or too thin to plan from (missing order, missing branch conditions,
vague content), ask a follow-up question before producing the plan — do not fill gaps with
invented content and present it as the developer's intent.

---

## Step 3 — Group into Phases

Group pages into delivery phases, whichever mode was used:
- Each phase should be a coherent, demoable chunk of the journey (e.g. "Phase 1: start page +
  eligibility check", not an arbitrary even split).
- Every page from Step 2A/2B must appear in exactly one phase.
- Phases are built in order by `prototype-scaffold-and-build` — later phases assume earlier ones
  exist and are navigable.

---

## Step 4 — Surface Open Items

Any legacy element with no direct GDS equivalent, any ambiguous branch, or any flavour-specific
limitation (see `prototype-scaffold-and-build` for `html`-flavour limitations) goes into an
`openItems` list with a proposed resolution. These are not blockers — the plan still proceeds —
but they must be visible to the developer and repeated in `PROTOTYPE-LOG.md`.

---

## Outputs

| Output | Description |
|---|---|
| `legacy-ui-migration-plan.json` | *(Migration mode only)* Full mapping from every legacy page to its GDS pattern, grouped into phases |
| `prototype-build-plan.json` | The plan actually built — page list, GDS pattern per page, journey order and branches, phases, open items. Produced in both modes. |

### JSON Schema (excerpt) — `prototype-build-plan.json`
```json
{
  "source": "legacy | greenfield",
  "flavour": "nodejs-nunjucks | html",
  "phases": [
    {
      "phase": 1,
      "name": "Start page + eligibility journey",
      "pages": [
        {
          "pageId": "start",
          "title": "Apply for a licence",
          "pattern": "start-page",
          "legacyRoute": "/Start.aspx",
          "next": "eligibility-1"
        },
        {
          "pageId": "eligibility-1",
          "title": "Are you a UK resident?",
          "pattern": "govuk-radios question page",
          "legacyRoute": "/EligibilityCheck.aspx",
          "branches": [
            { "condition": "No", "next": "not-eligible" },
            { "condition": "Yes", "next": "eligibility-2" }
          ]
        }
      ]
    }
  ],
  "openItems": [
    {
      "item": "Legacy dashboard widget on /Summary.aspx has no direct GDS equivalent",
      "proposedResolution": "Use govuk-summary-list plus govuk-tag for status; confirm with developer before building"
    }
  ]
}
```

---

## Constraints

- Do not begin `prototype-scaffold-and-build` until `prototype-build-plan.json` exists and every
  legacy page (migration mode) has been placed in a phase.
- Never invent bespoke UI to fill an unmapped legacy element — record it as an open item instead.
- Never guess at journey order or branch conditions in greenfield mode — ask instead.
