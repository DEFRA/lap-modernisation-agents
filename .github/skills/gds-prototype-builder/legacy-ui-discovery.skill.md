# Skill: legacy-ui-discovery

## Purpose
Inventory the complete UI layer of an existing application — every page, every element on it,
and how pages connect into journeys — regardless of the tech stack it's built on. This is a
read-only pass: nothing is built or changed here. Its output is what `prototype-plan` turns into
a phased plan, and what later lets a reviewer check that no page or journey step got lost on the
way to the new prototype.

## Trigger Conditions
- Runs only when `intake-and-setup` recorded a `referenceProjectPath` (legacy source).
- Skipped entirely for greenfield builds — `prototype-plan` reads `prompts` instead.

---

## Step 1 — Identify the UI Layer, Any Tech Stack

Scan `referenceProjectPath` for view/template/markup files regardless of framework:

| Stack | Look For |
|---|---|
| .NET WebForms | `*.aspx`, `*.ascx`, `*.master` |
| .NET MVC / Razor Pages | `*.cshtml` |
| Ruby on Rails | `*.erb`, `*.haml` |
| Node/Express | `*.ejs`, `*.pug`, `*.njk`, `*.hbs` |
| React/Vue/Angular SPA | `*.jsx`, `*.tsx`, `*.vue`, component folders |
| Plain/static | `*.html` |

Also note the app's routing layer (`Global.asax`/`RouteConfig`, `routes.rb`, `app.js`/router
files, React Router config, etc.) — this is what tells you how pages actually link together,
which matters more than file layout for journey order.

---

## Step 2 — Catalogue Every Page

For each page/view found, record:
- **Route/URL** (or entry point, for SPA components without a literal route).
- **Purpose** — one line, in plain English, of what the page is for.
- **Every element on it** — inputs (with their labels/names), buttons and their actions, tables,
  status indicators, error/validation messages, conditional content (things shown/hidden based on
  a prior answer).
- **Position in the journey** — what page(s) lead to it, and what it leads to next, including
  every branch (validation failure, conditional next-step, "back" behaviour).

Do this for **every page in scope**, not a representative sample — a page skipped here is a page
that will be silently missing from the new prototype.

---

## Step 3 — Map Journeys, Not Just Pages

Group the catalogued pages into journeys — a journey is a start-to-finish path a user actually
takes (e.g. "apply for a licence: start → eligibility → details → upload → check answers →
confirmation"). Record:
- The journey's start and end points.
- Every branch point and what triggers it.
- Any point where the legacy app shows the same page with materially different content based on
  earlier answers — this needs to become an explicit conditional in the new prototype's plan, not
  a single flattened page.

This is the piece that preserves "journey essence" — the new prototype must let a user take the
same decisions in the same order, even though every page is rebuilt with GDS components.

---

## Outputs

| Output | Description |
|---|---|
| `legacy-ui-inventory.json` | Every page found: route, purpose, elements, and journey position |

### JSON Schema (excerpt)
```json
{
  "referenceProjectPath": "C:\\Projects\\legacy-claims-app",
  "techStack": "ASP.NET WebForms",
  "pages": [
    {
      "route": "/EligibilityCheck.aspx",
      "purpose": "Ask three eligibility questions before allowing an application to start",
      "elements": [
        { "type": "radio-group", "name": "isResident", "label": "Are you a UK resident?" },
        { "type": "button", "name": "btnNext", "label": "Continue" }
      ],
      "journey": {
        "journeyName": "apply-for-licence",
        "precedingPages": ["/Start.aspx"],
        "nextPages": [
          { "condition": "isResident = No", "target": "/NotEligible.aspx" },
          { "condition": "isResident = Yes", "target": "/ApplicantDetails.aspx" }
        ]
      }
    }
  ],
  "journeys": [
    {
      "name": "apply-for-licence",
      "start": "/Start.aspx",
      "end": "/Confirmation.aspx",
      "branchPoints": ["/EligibilityCheck.aspx"]
    }
  ]
}
```

---

## Constraints

- This skill is **read-only** — it makes no changes to the reference project or the new prototype.
- Every page found must appear in `legacy-ui-inventory.json` — none may be summarised away or
  sampled out because the application is large. If the reference project is very large, say so
  explicitly and propose scoping to specific journeys with the developer rather than silently
  truncating the inventory.
- Do not begin `prototype-plan` until this inventory is complete.
