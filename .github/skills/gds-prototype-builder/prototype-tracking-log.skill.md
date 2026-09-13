# Skill: prototype-tracking-log

## Purpose
Record what just happened — inside the prototype's own folder, and centrally in this repo —
so every prototype this agent has ever touched stays traceable, even across separate sessions
and separate developers.

## Trigger Conditions
- **Always runs last**, regardless of whether preceding skills completed fully or left open items.

---

## Step 1 — Write or Update the Per-Project Log

At `<outputPath>\<projectName>\PROTOTYPE-LOG.md`, write (for a new project) or append a dated
entry (for a continuation run) covering:

- **Flavour**: `nodejs-nunjucks` or `html`.
- **Source**: legacy reference path, or a summary of the prompts used.
- **Pages built this run**: list, with their GDS pattern and phase.
- **Journey coverage**: which phases from `prototype-build-plan.json` are built vs still pending.
- **Decisions made**: any legacy-to-GDS mapping choice that wasn't a direct 1:1 (e.g. a legacy
  page split into three question pages).
- **Open items / needs sign-off**: everything carried over from `openItems` in the plan, plus
  anything found only during the build.

Keep this file readable by a human picking up the project cold — it is the project's own record,
independent of this repo.

---

## Step 2 — Append to the Central Registry

Append one row to `.github/docs/gds-prototype-builder-registry.md` in this repo (create the table
if this is the very first run ever recorded). Never rewrite or remove a prior row — this file is
an append-only history across every prototype this agent has generated, for every developer.

| Column | Value |
|---|---|
| Date | Run date, `YYYY-MM-DD` |
| Project name | `projectName` |
| Output path | `<outputPath>\<projectName>` |
| Flavour | `nodejs-nunjucks` or `html` |
| Source | `legacy: <referenceProjectPath>` or `greenfield` |
| Phases built | e.g. `1 of 3` |
| Status | `in progress`, `complete`, or `blocked — see PROTOTYPE-LOG.md` |

---

## Outputs

| Output | Description |
|---|---|
| `<outputPath>\<projectName>\PROTOTYPE-LOG.md` | Per-project human-readable record, created or appended |
| `.github/docs/gds-prototype-builder-registry.md` | One new append-only row for this run |

---

## Constraints

- This skill must run even if `prototype-scaffold-and-build` only partially completed — record
  what was built and what wasn't, rather than staying silent.
- Never remove or edit a previous row in the central registry — corrections are new rows, not
  rewrites, so the history stays honest.
- Never let the central registry go out of sync with reality — if a project folder no longer
  exists at its recorded path (moved or deleted outside this agent), note that in a new row rather
  than silently leaving the stale row unexplained.
