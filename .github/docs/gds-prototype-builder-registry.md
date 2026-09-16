# GDS Prototype Builder — Central Registry

Append-only log of every prototype the `gds-prototype-builder` agent has generated, across every
developer and every run. Written to by the `prototype-tracking-log` skill. Never edit or remove a
row — corrections are new rows.

Each prototype also keeps its own `PROTOTYPE-LOG.md` inside its own output folder with full detail
(pages built, decisions, open items). This file is the cross-project index only.

| Date | Project name | Output path | Flavour | Source | Phases built | Status |
|---|---|---|---|---|---|---|
| 2026-09-14 | cdc-prototype | C:\Users\sa000104\Fujale-Space\Projects\LAPS\Codebase\D2R2\cdc-prototype | html | legacy: C:\Users\sa000104\Fujale-Space\Projects\LAPS\Codebase\D2R2\D2R2-2026-08-17 | 0 of 6 | in progress — discovery + plan complete, build not started |
| 2026-09-14 | cdc-prototype | C:\Users\sa000104\Fujale-Space\Projects\LAPS\Codebase\D2R2\cdc-prototype | html | legacy: C:\Users\sa000104\Fujale-Space\Projects\LAPS\Codebase\D2R2\D2R2-2026-08-17 | 1 of 6 (Phase 1 complete, + 2 extra Phase 2 pages built early as design-signoff references) | in progress — design sign-off subset built (govuk-frontend 6.5.0, APHA logo, GOV.UK service navigation), awaiting business sign-off before remaining phases |
| 2026-09-15 | ptl-internal-prototype | C:\Users\sa000104\Fujale-Space\Projects\LAPS\Codebase\PTLIMS\ptl-internal-prototype | html | legacy: C:\Users\sa000104\Fujale-Space\Projects\LAPS\Codebase\PTLIMS\proficiency-testing-2026-08-17 (ProficiencyTestingWeb) | 1 of 7 (Home + Scheme List built; legacy HTML elements kept as-is, restyled with govuk-frontend 6.5.1) | in progress — 2-page subset built at developer request, remaining ~78 legacy pages inventoried and phased but not yet built |
