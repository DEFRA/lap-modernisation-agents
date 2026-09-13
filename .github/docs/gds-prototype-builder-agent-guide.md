# GDS Prototype Builder Agent — What It Does & Change Log

**File:** `.github/agents/gds-prototype-builder.agent.md`
**Last reviewed:** 2026-09-13
**Owner:** LAP Civica Migration Team
**Standards alignment:** Defra SDS · Defra AI Toolkit — Deliver with AI · GOV.UK Design System

---

## What This Agent Does

### Overview

The **GDS Prototype Builder Agent** scaffolds a clickable, functional GOV.UK Design System
prototype from scratch — no business logic, no database, nothing real behind it. It supports two
independent flavours: the official Node.js + Nunjucks GOV.UK Prototype Kit, and a pure
HTML/CSS/vanilla-JS build with no templating engine at all, for developers who need output usable
wherever only plain HTML syntax is accepted. It can optionally mine an existing legacy
application's UI layer — any tech stack — to inventory every page and journey and carry them
across into GDS components without losing the original journey's intent, or it can build entirely
from developer prompts.

This is a **different job** from the [`gds-ui` agent](./../agents/gds-ui.agent.md): `gds-ui`
reviews and fixes GDS compliance on real, existing application code. `gds-prototype-builder`
builds a throwaway prototype — useful for user research, stakeholder walkthroughs, or deciding
what a legacy app's UI should become before committing to the real rebuild.

---

### Flavours

| Flavour | What it is | Layout maintenance | Runtime dependency for the developer |
|---|---|---|---|
| `nodejs-nunjucks` | The real GOV.UK Prototype Kit, installed via `npx govuk-prototype-kit@latest create` | Shared Nunjucks layout, live-rendered | Node.js, `npm run dev` |
| `html` | Pure HTML/CSS/vanilla-JS — no Nunjucks, no Prototype Kit, no templating engine anywhere in the output or the build process | Shared plain-HTML partials (header/nav/footer), assembled into each page by hand | None — open the file or serve the folder with any static file server |

These are independent build paths, not one build compiled two ways. The `html` flavour exists
specifically for output that must be usable wherever only plain HTML syntax is accepted — it must
never contain templating syntax, and Nunjucks/the Prototype Kit must never be invoked while
generating it. Layout still avoids hand-duplication in this flavour: shared plain-HTML partial
fragments are the single source every page is assembled from.

---

### Skills (Executed in Order)

| Order | Skill | Purpose |
|---|---|---|
| 1 | `intake-and-setup` | Ask output path, project name, flavour, and source (legacy reference or developer prompts) |
| 2 | `legacy-ui-discovery` | *(Conditional)* Inventory every legacy page, element, and journey, any tech stack |
| 3 | `prototype-plan` | Produce a phased page-by-page GDS mapping plan |
| 4 | `prototype-scaffold-and-build` | Scaffold the chosen flavour and build every page/journey |
| 5 | `prototype-tracking-log` | Write the per-project log and update the central registry (always runs last) |

---

### Inputs Required

| Parameter | Required | Description | Example |
|---|---|---|---|
| `outputPath` | ✅ Yes | Absolute path to the parent folder | `C:\Projects\prototypes` |
| `projectName` | ✅ Yes | Kebab-case project folder name | `claims-service-prototype` |
| `flavour` | ✅ Yes | `nodejs-nunjucks` or `html` | `nodejs-nunjucks` |
| `referenceProjectPath` | No | Legacy application to mine for its UI layer | `C:\Projects\legacy-claims-app` |
| `prompts` | Required if no reference project | Free-text pages/journeys wanted | "Start page, eligibility check, upload evidence, check answers, confirmation" |

---

### Outputs Produced

| Output | Path | Description |
|---|---|---|
| Prototype project | `<outputPath>\<projectName>\` | The runnable/openable prototype |
| Legacy UI Inventory | `prototype-reports\legacy-ui-inventory.json` | Pages/elements/journeys found (legacy runs only) |
| Legacy-to-GDS Migration Plan | `prototype-reports\legacy-ui-migration-plan.json` | Phased mapping (legacy runs only) |
| Prototype Build Plan | `prototype-reports\prototype-build-plan.json` | The plan actually built |
| Per-project log | `PROTOTYPE-LOG.md` | Human-readable record for this specific prototype |
| Central registry | `.github/docs/gds-prototype-builder-registry.md` | Append-only row per prototype, across every project |

> **Note:** Generated prototypes are written to the developer-supplied `outputPath`, outside this
> repository, and are never committed here. Only the central registry row lives in this repo.

---

### Guardrails Summary

**The agent will:**
- Always ask for output path, project name, flavour, and source — never default or guess
- Preserve every legacy page and journey step in the plan, even ones flagged as open items
- Use only official GOV.UK Design System components and patterns in both flavours
- Keep layout centrally maintained (one shared template), never hand-duplicated per page
- Update the per-project log and the central registry on every run, including partial/blocked ones

**The agent will never:**
- Add business logic, a database, ORM, or real authentication to a prototype
- Seed a prototype with real user, claimant, or citizen data
- Silently drop a legacy page or journey step
- Commit a generated prototype into this repository
- Invent bespoke UI when a Design System component or pattern exists

---

### Compliance Profile

| Dimension | Classification / Status |
|---|---|
| AI Toolkit risk level | MEDIUM |
| Human oversight required | Yes — review before sharing a prototype for user research or sign-off |
| Defra SDS standards applied | GitHub Copilot guide, Common coding standards, Security standards |

---

## Versioning

- Current version: **v1**
- Version folder: `.github/agents/versions/gds-prototype-builder/v1/`
- Strategy: [`.github/docs/agent-versioning-strategy.md`](./agent-versioning-strategy.md)
- Do not modify v1 directly for enhancements — create `v2/` per the versioning strategy.

---

## Change Log

### v1.0 — 2026-09-13 — Initial Guide

Initial creation of the GDS Prototype Builder agent, its five-skill pipeline, and the central
prototype registry.

---

## References

- [`.github/agents/gds-prototype-builder.agent.md`](./../agents/gds-prototype-builder.agent.md) — agent definition
- [`.github/agents/gds-ui.agent.md`](./../agents/gds-ui.agent.md) — GDS compliance agent for real, existing code
- [`.github/docs/gds-prototype-builder-registry.md`](./gds-prototype-builder-registry.md) — central prototype registry
- GOV.UK Design System: https://design-system.service.gov.uk/
- GOV.UK Prototype Kit docs: https://prototype-kit.service.gov.uk/docs/
- [Defra SDS — GitHub Copilot guide](https://defra.github.io/software-development-standards/guides/github_copilot/)
- [Defra SDS — Common coding standards](https://defra.github.io/software-development-standards/standards/common_coding_standards/)
- [Defra SDS — Security standards](https://defra.github.io/software-development-standards/standards/security_standards/)
- [Defra AI Toolkit — Deliver with AI](https://digital.defra.gov.uk/ai-toolkit/deliver-with-ai)
- [Defra AI Config Examples — Agents guide](https://github.com/DEFRA/defra-ai-config-examples/blob/main/pages/agents/index.md)

---

*This document is maintained alongside `.github/agents/gds-prototype-builder.agent.md`. Update the change log and "Last reviewed" date whenever the agent is modified.*
