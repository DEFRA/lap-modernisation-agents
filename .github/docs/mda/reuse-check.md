# Reuse check (spec §2)

Performed against `.github/agents/` and `.github/skills/` before building anything bespoke.

| Responsibility | Existing asset | Decision |
|---|---|---|
| Requirements from an ADO story | `requirements-to-scrum-board` (documents → CSV for bulk upload, no ADO read) | **Bespoke** `requirements-agent` (thin); existing agent not applicable |
| Legacy discovery | `pdf-discovery`, `e2e-baseline-page-discovery`, `db-migration` schema-analysis, `identity-migration` | **Bespoke** `legacy-analyst` for cross-cutting story scope + factor counts; **references** domain agents when the story touches their domain |
| Design / test plan | `documentation-lld` (fills LLD docx), `.github/instructions/*`, domain guides, `dotnet-test-automation-and-quality-agent` | **Bespoke** `target-architect` (complexity scoring is new); LLD and conventions **reused by reference** |
| Code writing | `dotnet-framework-upgrade`, `dotnet-code-refactor`, `service-modernisation-wcf-asmx-to-rest`, `db-migration`, `ssis-adf-convert-agent`, `identity-migration*`, `pdf-*`, `windows-service-to-lambda`, `gds-ui` | **Reused**: `build-engineer` is a router/incremental builder that delegates per task type |
| Tests | `dotnet-test-automation-and-quality-agent`, `playwright-tester-agent` | **Reused** by build-engineer and quality-gate-agent |
| Security | `security-code` | **Reused** by quality-gate-agent |
| Sonar, performance, gate aggregation | none | **Bespoke** (in `quality-gate-agent` + `mda.py sonar`) |
| Commit/PR packaging | none | **Bespoke** `release-packager` |
| QA scenario authoring | `e2e-baseline-scenario-synthesiser` (automated Playwright baselines for Web Forms) | **Bespoke** `qa-authoring-agent`; automation coverage cross-referenced |
| Reporting | none | **Bespoke** `reporting-agent` over `mda.py report` |

Re-run this check when new agents are added to the repo, and update this table.
