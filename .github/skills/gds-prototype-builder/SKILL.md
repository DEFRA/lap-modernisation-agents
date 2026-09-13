---
# Last reviewed: 2026-09-13 — review quarterly, when defra-ai-config-examples is updated, or when GOV.UK Design System / Prototype Kit guidance changes
skill:
  id: gds-prototype-builder
  name: GDS Prototype Builder
  version: 1.0.0
  owner: Implementation Team
  intent: >
    Scaffolds a clickable, functional GOV.UK Design System prototype — either the official
    Node.js + Nunjucks GOV.UK Prototype Kit, or a pure HTML/CSS/vanilla-JS build with no
    templating engine, server-side logic, or database. Optionally mines an existing legacy application's UI
    layer (any tech stack) to inventory every page and journey, then produces a phased plan that
    carries the whole journey across into GDS components without losing its essence. Otherwise
    builds from developer prompts on a greenfield basis. Tracks every prototype generated, per
    project and centrally.
  recommended_agent: gds-prototype-builder
  execution_model: instruction-only with sequential skill gates
  scope:
    includes:
      - Interactive intake of output path, project name, flavour, and source (legacy or prompts)
      - Legacy UI layer discovery across any tech stack (pages, elements, journeys)
      - Phased legacy-to-GDS component mapping plan, preserving journey order and branching
      - Greenfield page/journey planning from free-text developer prompts
      - Official GOV.UK Prototype Kit scaffolding (Node.js + Nunjucks) via the real installer
      - Pure HTML/CSS/vanilla-JS prototype build, assembled from shared plain-HTML partials, with vendored govuk-frontend assets — no templating engine involved
      - Clickable navigation and branching between pages in both flavours
      - Session-only "remembered" state (kit data store, or re-echoed hidden fields) — prototype only
      - Per-project prototype log and central cross-project registry tracking
    excludes:
      - Any business logic, data persistence, ORM, or real database
      - Real authentication or authorisation
      - Production deployment of the prototype
      - Migrating a legacy application's actual working code (this only rebuilds the UI layer as a prototype)
      - Committing generated prototypes into this repository (they live at the developer's outputPath)
      - Bespoke UI components not covered by the GOV.UK Design System, without explicit sign-off
  inputs_required:
    - outputPath: "Absolute path to the parent folder the prototype project will be created under"
    - projectName: "Name for the new prototype project folder (kebab-case)"
    - flavour: "nodejs-nunjucks (official GOV.UK Prototype Kit) or html (pure HTML/CSS/vanilla-JS, no templating engine, no server)"
    - referenceProjectPath: "Optional — absolute path to a legacy/existing application to mine for its UI layer"
    - prompts: "Required if referenceProjectPath is not given — free-text description of pages/journeys wanted"
  outputs:
    - "<outputPath>/<projectName>/ — the runnable or openable prototype itself"
    - "<outputPath>/<projectName>/prototype-reports/legacy-ui-inventory.json — legacy pages/elements/journeys (reference-project runs only)"
    - "<outputPath>/<projectName>/prototype-reports/legacy-ui-migration-plan.json — phased legacy-to-GDS mapping (reference-project runs only)"
    - "<outputPath>/<projectName>/prototype-reports/prototype-build-plan.json — the page/journey plan actually built"
    - "<outputPath>/<projectName>/PROTOTYPE-LOG.md — per-project human-readable record"
    - ".github/docs/gds-prototype-builder-registry.md — append-only central registry row for this run"
  success_criteria:
    - Every page in the build plan exists, is styled with GOV.UK Design System components, and is reachable by clicking through the prototype from its start page
    - nodejs-nunjucks flavour: kit installs and starts cleanly (npm install, npm run dev)
    - html flavour: opens/serves with zero Node, server-side, or templating-engine dependency; every file is plain HTML/CSS/JS with no templating syntax in it; layout was assembled from a single shared set of plain-HTML partials, not hand-duplicated per page
    - Every legacy page/journey step (reference-project runs) appears in exactly one phase of the plan — none silently dropped
    - PROTOTYPE-LOG.md and the central registry are both updated before the run ends
  safety:
    - Never add business logic, a database, or real authentication — session-only prototype state is the ceiling.
    - Never silently choose flavour, output path, project name, or source — always confirm with the developer.
    - Never invent bespoke UI when a Design System component/pattern exists — escalate instead.
    - Never seed a prototype with real user, claimant, or citizen data — fabricated example content only.
    - Never commit a generated prototype into this repository.
    - Never drop a legacy page or journey step from the plan, even when flagged as a future phase.
---

# GDS Prototype Builder (Skill)

This skill package scaffolds GOV.UK Design System prototypes end to end: intake, optional legacy
UI discovery, planning, build, and tracking. It supports two independent flavours — the official
Node.js + Nunjucks GOV.UK Prototype Kit, and a pure HTML/CSS/vanilla-JS build with no templating
engine at all, for developers who need output usable wherever only plain HTML syntax is accepted.

Execution model: **instruction-only with sequential skill gates**.

---

## Flavours

| Flavour | What it is | Layout maintenance | Runtime dependency for the developer |
|---------|-----------|---------------------|----------------------------------------|
| `nodejs-nunjucks` | The real [GOV.UK Prototype Kit](https://prototype-kit.service.gov.uk/docs/) | Shared Nunjucks layout, live-rendered | Node.js, `npm run dev` |
| `html` | Pure HTML/CSS/vanilla-JS — no templating engine involved at any point | Shared plain-HTML partials (header/nav/footer), assembled into each page by hand, not by a templating engine | None — open the file or serve the folder with any static file server |

> These two flavours are **independent build paths**, not one build compiled two ways. The
> `html` flavour exists specifically for cases where only plain HTML syntax is usable — it must
> never contain Nunjucks (or any other templating) syntax, and Nunjucks/the Prototype Kit must
> never be invoked while generating it. Layout is still kept in one place for `html` via shared
> plain-HTML partial fragments that every page is assembled from — never hand-duplicate the same
> header/footer/nav markup independently inside every page file.

---

## Skills (Playbooks)

| Order | Skill File | Purpose | Key Inputs | Key Outputs |
|-------|-----------|---------|------------|--------------|
| 1 | [intake-and-setup.skill.md](./intake-and-setup.skill.md) | Ask output path, project name, flavour, and source; create the project folder | Developer answers | Project folder scaffold, confirmed parameters |
| 2 | [legacy-ui-discovery.skill.md](./legacy-ui-discovery.skill.md) | *(Conditional)* Inventory every legacy page, element, and journey, any tech stack | `referenceProjectPath` | `legacy-ui-inventory.json` |
| 3 | [prototype-plan.skill.md](./prototype-plan.skill.md) | Produce a phased page-by-page GDS mapping plan, from legacy inventory or from prompts | `legacy-ui-inventory.json` or `prompts` | `legacy-ui-migration-plan.json` (if applicable), `prototype-build-plan.json` |
| 4 | [prototype-scaffold-and-build.skill.md](./prototype-scaffold-and-build.skill.md) | Scaffold the chosen flavour and build every page/journey from the plan | `prototype-build-plan.json`, `flavour` | The prototype project itself |
| 5 | [prototype-tracking-log.skill.md](./prototype-tracking-log.skill.md) | Write the per-project log and update the central registry | All prior outputs | `PROTOTYPE-LOG.md`, registry row |

> **Skill 5 always runs last**, even if a preceding skill blocked or was left partially built. Anything incomplete is recorded as an open item, not silently dropped.

---

## Execution Sequence

```
[START]
  │
  ▼
1. intake-and-setup            ← ASKS; never defaults path, name, flavour, or source
  │  flavour = nodejs-nunjucks | html
  │  source  = legacy (referenceProjectPath) | greenfield (prompts)
  ▼
2. legacy-ui-discovery         ← ONLY if source = legacy; READ-ONLY inventory pass
  │  produces legacy-ui-inventory.json
  ▼
3. prototype-plan              ← reads inventory OR prompts; produces phased build plan
  │  every legacy page/journey step must land in exactly one phase
  ▼
4. prototype-scaffold-and-build ← reads flavour; selects Mode A / B
  │  Mode A = nodejs-nunjucks  (official kit installer, live routes.js + Nunjucks)
  │  Mode B = html             (plain-HTML partials assembled by hand → flat files + vendored assets, no templating engine)
  ▼
5. prototype-tracking-log      ← ALWAYS runs; writes PROTOTYPE-LOG.md + central registry row
  │
  ▼
[END]
```

### Blocking Issue Policy

If any skill hits something it cannot resolve (a legacy element with no GDS equivalent, an
ambiguous journey branch, a flavour-specific limitation):
1. Log the issue in that skill's JSON output with a concrete description and a recommended next step.
2. **Do not silently skip or improvise** — propose the closest Design System pattern and flag it for developer sign-off.
3. `prototype-tracking-log` surfaces every open item in `PROTOTYPE-LOG.md` under "Open items / needs sign-off."

---

## Output Contract

| Output | Path | Description |
|--------|------|--------------|
| Prototype project | `<outputPath>\<projectName>\` | The runnable/openable prototype |
| Legacy UI Inventory | `<outputPath>\<projectName>\prototype-reports\legacy-ui-inventory.json` | Pages, elements, journeys found in the reference project |
| Legacy-to-GDS Migration Plan | `<outputPath>\<projectName>\prototype-reports\legacy-ui-migration-plan.json` | Phased plan mapping every legacy page to GDS components |
| Prototype Build Plan | `<outputPath>\<projectName>\prototype-reports\prototype-build-plan.json` | The plan actually built, both flavours and both source modes |
| Per-project log | `<outputPath>\<projectName>\PROTOTYPE-LOG.md` | Human-readable record for this specific prototype |
| Central registry entry | `.github/docs/gds-prototype-builder-registry.md` | Append-only row for this run, in this repo |

---

## Constraints Summary

| Rule | Applies To |
|------|-----------|
| Never default output path, project name, flavour, or source — always ask | Skill 1 |
| Never begin building before the plan exists | Skills 2, 3, 4 |
| Never drop a legacy page/journey step from the plan | Skill 3 |
| Never hand-duplicate layout markup per page — author once, render live or assemble from shared partials | Skill 4 |
| Never use Nunjucks, the Prototype Kit, or any templating engine to produce the `html` flavour | Skill 4 |
| Never add business logic, persistence, or real auth in either flavour | Skill 4 |
| Never seed real user/claimant/citizen data — fabricated example content only | Skill 4 |
| Never commit the generated prototype into this repository | All |
| Always update PROTOTYPE-LOG.md and the central registry before finishing | Skill 5 |

---

## Standards

This skill is loaded by the [gds-prototype-builder agent](./../../agents/gds-prototype-builder.agent.md). Component and pattern choices follow the same Design System rules enforced by the [gds-ui agent](./../../agents/gds-ui.agent.md). All generated prototypes are subject to human review before use in user research or stakeholder sign-off, per the [Defra AI Toolkit — Deliver with AI](https://digital.defra.gov.uk/ai-toolkit/deliver-with-ai). Follows [Defra SDS — GitHub Copilot guide](https://defra.github.io/software-development-standards/guides/github_copilot/) and [Defra SDS — Common coding standards](https://defra.github.io/software-development-standards/standards/common_coding_standards/).
