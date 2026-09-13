# Generic AI Agents for Legacy Modernisation

This repository contains reusable AI agents for legacy application modernisation across diverse enterprises. Each agent follows the [GitHub Copilot custom agents](https://github.com/github/awesome-copilot/blob/main/docs/README.agents.md) and [Agent Skills open standard](https://github.com/github/awesome-copilot) conventions.

Compatible with: GitHub Copilot, Claude Code, Codex CLI, Gemini CLI, Cursor, Windsurf, and other SKILL.md-compatible agent runtimes.

> **Note:** The `security-code` agent is under active testing on the `test/security-agent` branch.

---

## Total Agent Count by Domain

> Sub-agents invoked internally by orchestrators are not counted here. Total reflects user-invocable top-level agents only.

| Domain | Count | Top-Level Agents |
|---|---|---|
| Database & Data Integration | 2 | Database Migration, SSIS to ADF Migration |
| DevOps & CI/CD | 1 | DevOps Pipeline Modernizer |
| Documentation | 1 | Documentation LLD |
| .NET Application Modernisation | 4 | .NET Framework Upgrade, Code Refactor, Service Modernisation (WCF/ASMX→REST), Windows Service to Lambda |
| Identity & Authentication | 1 | Identity Migration Orchestrator *(routes internally to SAML and OIDC sub-agents)* |
| PDF & Reporting | 2 | PDF Migration Orchestrator *(routes internally to Discovery, Infrastructure, Converter, Validation sub-agents)*, PDF Report Modernizer |
| Testing & Quality | 3 | .NET Test Automation, Playwright Tester, E2E Baseline Orchestrator *(routes internally to 6 sub-agents)* |
| Security | 1 | Security Code Analysis |
| Project Management | 1 | Requirements to Scrum Board |
| Utilities | 1 | GraphAPI Send Mail |
| UI Compliance | 1 | GDS UI Compliance |
| UI Prototyping | 1 | GDS Prototype Builder |
| **Total** | **19** | |

## Available Agents

### Database Migration Agent

**Entry point**: `.github/agents/db-migration.agent.md`

Helps engineers migrate databases between platforms — Oracle, SQL Server, MySQL, PostgreSQL, MongoDB, DynamoDB, and more. Covers the full migration lifecycle: schema analysis, data model advisory, schema conversion, compatibility fixing, performance tuning, validation, and reporting.

**Modes**:

- **Auto mode** — `@db-migration migrate my Oracle database to PostgreSQL` — runs all phases sequentially, pausing after analysis for confirmation.
- **Manual mode** — `@db-migration analyse my database` — runs a single phase.

**Skills** (under `.github/skills/db-migration/`):

| Skill                  | Purpose                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| `schema-analysis`      | Introspect source database: tables, columns, constraints, indexes, views, procedures, row counts |
| `data-model-advisory`  | Advise on data model design for paradigm-shift migrations (RDBMS ↔ Document DB)                  |
| `schema-conversion`    | Convert DDL from source to target platform with type mapping and procedural code translation     |
| `compatibility-fixing` | Catch and fix dialect-specific quirks, reserved words, collation issues                          |
| `performance-tuning`   | Review indexes, query plans, partitioning, and DB-specific configuration                         |
| `migration-validation` | Verify row counts, schema structure, constraints, and functional equivalence                     |
| `migration-reporting`  | Generate a comprehensive migration playbook and final report                                     |

Reference files in each skill grow over time as the team documents new migration patterns and quirks from real engagements.

---

### DevOps Pipeline Modernizer

**Entry point**: `.github/agents/devops-pipeline-modernizer.agent.md`

Modernizes CI/CD with reusable templates, branching strategy, environment configuration, and LLD-to-Bicep IaC generation.

**Skills**: `.github/skills/devops-pipeline-modernizer/`

---

### Identity Migration (.NET)

**Entry point**: `.github/agents/identity-migration.agent.md`
**Architecture diagram**: [`.github/docs/identity-migration/agent-architecture.md`](.github/docs/identity-migration/agent-architecture.md)

Migrates modern ASP.NET Core applications (.NET 8, .NET 10, and newer) from Windows Authentication to Azure Entra ID. Also wires greenfield SAML2 or OIDC integrations from scratch. Uses an orchestrator + two specialist sub-agents.

**Sub-agents**:

| Agent | Entry point | Purpose |
|-------|-------------|---------|
| Identity Migration Orchestrator | `.github/agents/identity-migration.agent.md` | Detects scenario and framework, runs shared scaffolding, routes to sub-agents, stitches output |
| SAML Sub-Agent | `.github/agents/identity-migration-saml.agent.md` | Sustainsys / ITfoxtec wiring, ACS handler, SLO bindings, session expiry, Windows Auth removal |
| OIDC Sub-Agent | `.github/agents/identity-migration-oidc.agent.md` | Microsoft.Identity.Web wiring, PKCE, silent renew, MSAL token cache, negative-path handlers |

**Supported scenarios**:

| Scenario | Starting point | Protocol |
|---|---|---|
| `WindowsAuthToSAML` | App uses `AddNegotiate()` | SAML 2.0 → Entra ID |
| `WindowsAuthToOIDC` | App uses `AddNegotiate()` | OIDC → Entra ID |
| `NewSAML` | No existing auth | SAML 2.0 → Entra ID |
| `NewOIDC` | No existing auth | OIDC → Entra ID |

**Skills** (under `.github/skills/identity-migration-dotnet/`):

| Skill | Purpose |
|-------|---------|
| `entra-auth-bootstrap-dotnet` | Entra ID startup bootstrap and app registration discovery |
| `claims-mapping-saml-to-entra` | Centralized SAML → Entra claims normalization |
| `token-lifecycle-dotnet` | Token validation, expiry handling, session lifecycle |
| `entra-config-validation` | Runtime issuer / audience / tenant alignment checks |
| `auth-testing-validation-dotnet` | xUnit test stubs per environment (Dev / Test / UAT / Prod) |

**Key outputs**:

- `ENTRA-REGISTRATION.md` — Entra ID app registration checklist (produced once by orchestrator)
- `appsettings.{Development|Test|UAT|Production}.json` — four-environment config stubs with placeholder values
- `Services/ClaimsMapper.cs` — `IClaimsTransformation` mapping Entra ID role/group claims to canonical app role names
- Updated `Program.cs` — SAML2 or OIDC middleware wired; Windows Auth wiring removed
- `Controllers/AccountController.cs` (OIDC) — thin sign-in / sign-out / access-denied wrappers
- xUnit test stubs for auth flows, role gates, and session lifecycle
- `summary.md` — per-migration tracking file (scenario, files changed, role map, verification checklist, risks)

**Test fixtures**: `.github/tests/fixtures/` — four synthetic codebases covering all scenarios. See [fixture README](.github/tests/fixtures/README.md).

---

### PDF Report Modernizer Agent (.NET)

**Entry point**: `.github/agents/pdf-report-modernizer.agent.md`

Modernises Crystal Reports (`.rpt`) into Azure-compatible PDF output using a `ReportDefinition.json`-driven pipeline. Removes all Crystal Reports runtime dependencies. Uses only free, open-source NuGet packages (DinkToPdf / QuestPDF Community). Targets .NET Framework 4.8 VB.NET / ASPX on Azure App Service.

**Skills**: `.github/skills/pdf-report-migration/`

---

### PDF Migration Orchestrator

**Entry point**: `.github/agents/pdf-migration-orchestrator.agent.md`

Orchestrates the full end-to-end migration pipeline for replacing a programmatic PDF library (TallPDF, iText, FastReport, PdfSharp, Syncfusion, Aspose, Crystal Reports) to an HTML-first approach using Razor views and Playwright headless PDF rendering.

**Sub-agents**:

| Agent | Entry point | Purpose |
|-------|-------------|---------|
| PDF Discovery | `pdf-discovery.agent.md` | Scan codebase and produce report inventory |
| PDF Infrastructure | `pdf-infrastructure.agent.md` | Set up Razor view pipeline and Playwright renderer |
| PDF Report Converter | `pdf-report-converter.agent.md` | Convert individual reports to Razor + CSS |
| PDF Validation | `pdf-validation.agent.md` | Validate output against original PDFs |

**Key outputs**:

- `report-inventory.json` — discovered reports and their metadata
- Razor view templates with CSS styling
- Playwright-based PDF rendering pipeline
- Validation reports comparing old vs new output

---

### Code Refactor Agent (.NET)

**Entry point**: `.github/agents/dotnet-code-refactor.agent.md`

Cleans and improves legacy code with a strong focus on maintainability, error handling, and structured logging. Runs five ordered skills: code cleanup → global exception handling → Application Insights logging → build validation → HTML report. Does not change business logic.

**Skills**: `.github/skills/dotnet-code-refactor/`

---

### Documentation - Low Level Design (LLD) Agent

**Entry point**: `.github/agents/documentation-lld.agent.md`

Translates High-Level Solution Architecture (HLSA) and High-Level Design (HLD) into build-ready Low-Level Design (LLD) documentation. Uses eight collaborating sub-agents: Architecture Decomposer, Component Specification, Security & Compliance, Data & Integration, Infrastructure & Environment, CI/CD Pipeline, Operations & Runbook, and Technical Specification Synthesizer.

**Key outputs**:

- Complete LLD document in DOCX format
- Mermaid diagrams for architecture and flows
- Component specifications with API contracts
- Infrastructure and deployment guidance
- Document generation summary with sections requiring manual review

---

### Security Code Analysis Agent

**Entry point**: `.github/agents/security-code.agent.md`

ITHC (IT Health Check) security findings scanner that combines SAST (Static Analysis), SCA (Software Composition Analysis), Secrets Scanning, IaC Review, and AI-assisted pattern detection to identify vulnerabilities across a project. Generates security findings reports aligned with the ITHC spreadsheet format used in UK Government engagements.

**Standards**: OWASP Top 10 (2021), CWE Top 25, NCSC Cyber Essentials, CVSSv3.1, PTES, NIST SP 800-115

**Scan modes**:

- `full` (default) — All security analysis layers
- `sast-only` — Static analysis only
- `secrets-only` — Secrets scanning only
- `iac-only` — Infrastructure as Code review only
- `sca-only` — Software Composition Analysis only

**Output formats**: CSV, XLSX, PDF, Markdown, JSON

**Key outputs**:

- Comprehensive security findings report with CVSSv3.1 scores
- OWASP / CWE / NCSC mapping
- Deduplicated vulnerabilities with remediation guidance
- ITHC-ready spreadsheet format

---

### Requirements to Scrum Board Agent

**Entry point**: `.github/agents/requirements-to-scrum-board.agent.md`

Transforms requirements documents (Word, Excel, PDF, Markdown, plain text) into a CSV file for bulk upload to Jira or Azure DevOps. Extracts one user story per requirement, derives epics by thematic grouping, and applies the correct schema and import instructions for the chosen platform. No API calls are made.

**Supported formats**: `.txt`, `.md`, `.docx`, `.pdf`, `.xlsx`, `.xls`, `.csv`, `.pptx`, pasted plain text

**Security safeguards**:

- Maximum 20 epics and 50 user stories per CSV
- Formula-injection prevention
- Content sanitisation
- Path validation
- Preview before write

**Key outputs**:

- CSV file ready for bulk import to Jira or Azure DevOps
- Epic and user story structure with proper field mapping
- Import instructions for the chosen platform

---

### GraphAPI Send Mail Agent

**Entry point**: `.github/agents/graphapi.agent.md`

Sends email messages using Microsoft Graph API. Designed for automation scenarios where an agent needs to deliver notifications, reports, or alerts. Supports attachments, CC/BCC, and both HTML and plain-text bodies. Uses OAuth2 client credentials flow via MSAL.

**Required permissions**: `Mail.Send` (Application) or `Mail.Send` (Delegated)

**Inputs**:

- Tenant ID, Client ID, Client Secret
- Sender email address
- Recipients (to, cc, bcc)
- Subject and body (HTML or plain text)
- Optional attachments (base64 encoded)

**Key outputs**:

- Success/failure status
- Detailed error diagnostics for troubleshooting
- Message ID for tracking

**Skills**: `.github/skills/graph-api-sendmail/`

---

### GDS UI Compliance Agent

**Entry point**: `.github/agents/gds-ui.agent.md`

Enforces GOV.UK Design System (GDS) and GOV.UK Service Standard on all user-facing work — building, reviewing, or modifying pages, components, forms, and templates. Apply before writing, while writing, and on review.

**Hard requirements**:

- Use `govuk-frontend` components (no hand-rolled CSS clones)
- Meet WCAG 2.2 AA accessibility standards
- Semantic HTML with proper heading hierarchy
- Forms follow "one thing per page" pattern
- GOV.UK page template with crown header and phase banner
- Plain English content in sentence case

**Skills**: `.github/skills/fix-gds-layout.skill.md`

**Key outputs**:

- GDS-compliant HTML markup
- Accessibility validation reports
- Component usage checklist
- Content style validation

---

### GDS Prototype Builder Agent

**Entry point**: `.github/agents/gds-prototype-builder.agent.md`
**Agent guide**: [`.github/docs/gds-prototype-builder-agent-guide.md`](.github/docs/gds-prototype-builder-agent-guide.md)
**Central registry**: [`.github/docs/gds-prototype-builder-registry.md`](.github/docs/gds-prototype-builder-registry.md)

Scaffolds a clickable, functional GOV.UK Design System prototype from scratch — either the official Node.js + Nunjucks GOV.UK Prototype Kit, or a pure HTML/CSS/vanilla-JS build with no templating engine, server-side logic, or database, for cases where only plain HTML syntax is usable. Can optionally analyse an existing legacy application's UI layer (any tech stack) to inventory every page and journey and carry them across into GDS components without losing the original journey's intent, or build from developer prompts on a greenfield basis.

> **When to use `gds-prototype-builder` vs `gds-ui`**: Use this agent to build a **new, throwaway clickable prototype** — for user research, stakeholder walkthroughs, or deciding what a legacy app's UI should become. Use [`gds-ui`](#gds-ui-compliance-agent) to review or fix GDS compliance on **real, existing application code**.

**Flavours**:

| Flavour | What it is | Runtime dependency |
|---|---|---|
| `nodejs-nunjucks` | The official GOV.UK Prototype Kit | Node.js, `npm run dev` |
| `html` | Pure HTML/CSS/vanilla-JS, no templating engine — assembled from shared plain-HTML partials so layout isn't hand-duplicated per page | None — open the file or serve the folder |

**Skills** (under `.github/skills/gds-prototype-builder/`):

| Skill | Purpose |
|-------|---------|
| `intake-and-setup` | Ask output path, project name, flavour, and source (legacy reference or developer prompts) |
| `legacy-ui-discovery` | *(Conditional)* Inventory every legacy page, element, and journey, any tech stack |
| `prototype-plan` | Produce a phased page-by-page GDS component mapping plan |
| `prototype-scaffold-and-build` | Scaffold the chosen flavour and build every page/journey from the plan |
| `prototype-tracking-log` | Write the per-project log and update the central registry (always runs last) |

**Key outputs**:

- The prototype project itself, at the developer's chosen `outputPath` (never committed to this repo)
- `legacy-ui-inventory.json` and `legacy-ui-migration-plan.json` — legacy runs only
- `prototype-build-plan.json` — the page/journey plan actually built
- `PROTOTYPE-LOG.md` — per-project record of pages built, decisions, and open items
- A row appended to the central registry for every prototype ever generated

---

### Repo Compliance Gatekeeper

**Entry point**: `.github/agents/repo-compliance-gatekeeper.agent.md`

Repository governance agent that enforces documentation standards for all agents. Automatically validates that every agent file in `.github/agents/` has corresponding documentation in `README.md`. Runs on every PR creation and update, blocking merges when documentation is missing or incomplete.

**Trigger**: Automatic on every check-in (PR creation, PR updates, commits to PR branches)

**Validation checks**:

- All `.agent.md` files in `.github/agents/` are documented in `README.md`
- Entry point paths match actual file locations
- Agent descriptions meet minimum quality standards (50+ characters)
- No undocumented agents are allowed

**Blocking behavior**:

- ✅ **PASS** — All agents documented → PR can merge
- ❌ **FAIL** — Missing documentation → PR blocked with clear error message listing undocumented agents

**Integration**:

- GitHub Actions workflow: `.github/workflows/validate-agent-documentation.yml`
- Local validation script: `.github/scripts/validate-agent-docs.ps1`
- Pre-commit hook installer: `.github/scripts/install-git-hooks.ps1`
- PR template checklist: `.github/PULL_REQUEST_TEMPLATE.md`

**Key outputs**:

- Validation reports showing documented/undocumented agents
- Blocking status (pass/fail with exit codes)
- Actionable error messages with remediation steps
- Links to `CONTRIBUTING.md` and `DOCUMENTATION_REQUIREMENTS.md`

**Documentation requirements**:

Each agent must have a README.md entry with:
- Agent name as heading (### format)
- Entry point path (`.github/agents/[filename]`)
- Description (minimum 50 characters)
- Key features or modes
- Skills reference (if applicable)
- Key outputs

See `CONTRIBUTING.md` for complete documentation standards and `DOCUMENTATION_REQUIREMENTS.md` for detailed requirements.

---
 
### SSIS to ADF Migration Agent
 
**Entry point**: `.github/agents/ssis-adf-convert-agent.md`
 
Converts SSIS packages to Azure Data Factory assets in three phases: SSIS analysis, ADF artifact conversion, and migration reporting.
 
**Skills**: `.github/skills/ssis-adf-convert/`
 
**Key outputs**:
 
- SSIS input/output/transformation analysis report
- ADF JSON artifacts (`factory`, `pipeline`, `dataset`, `linkedService`, `integrationRuntime`, `trigger`)
- `ARMTemplateForFactory.json` and `ARMTemplateParametersForFactory.json`
- `managed-identity-details.json` with RBAC action guidance
- Final migration report for engineering and stakeholders

---

### Service Modernisation Agent (WCF / ASMX → REST)

**Entry point**: `.github/agents/service-modernisation-wcf-asmx-to-rest.agent.md`

Converts legacy WCF and ASMX service contracts to modern REST APIs and direct in-process calls using a complexity-tiered migration strategy. Designed for large-scale service modernisation projects.

**Modes**:

- **`analyse`** — Introspect WCF/ASMX files, WSDL contracts, and operation signatures; classify services as Low/Medium/High complexity; output inventory with risk flags.
- **`plan`** — Interview for architectural and sequencing decisions; produce a zero-ambiguity modernisation plan with phase breakdown, effort estimates, and manual review gates.
- **`generate-low-medium`** — Generate ASP.NET Core REST controllers, request/response DTOs, OpenAPI annotations, and data-parity integration tests for Low and Medium-complexity services.
- **`review-high-complexity`** — Produce structured review briefs for High-complexity services (e.g., Tabulation, DistributionForComment) with domain logic analysis, risk assessment, and guided refactor recommendations (no auto-conversion).
- **`generate-inprocess`** — Generate direct in-process call adapters and CSLA BO wrappers for application services, preserving data-type fidelity.
- **`cleanup-project-references`** — Remove web references, WSDL/.disco/.map files, and orphaned `using` statements from project files.
- **`full-pipeline`** — End-to-end orchestration: analyse → plan → generate Low/Medium → review High-complexity → (optional) in-process transform → cleanup → report.

**Skills** (under `.github/skills/service-modernisation/`):

| Skill | Purpose |
|-------|---------|
| `service-analysis` | Parse WCF/ASMX contracts, extract operation signatures, assess complexity (Low/Medium/High) |
| `migration-planning` | Interview for architecture/sequencing, output zero-ambiguity plan with phases and risk gates |
| `rest-conversion-low-medium` | Generate REST controllers, DTOs, OpenAPI annotations for straightforward services |
| `high-complexity-review-brief` | Produce structured review guides for critical services requiring manual refactor |
| `inprocess-transformation-csla` | Generate adapters wrapping CSLA BOs for direct in-process calls (application) |
| `project-cleanup` | Remove obsolete web references and update project files |
| `data-parity-testing` | Generate integration tests comparing original ASMX output vs new REST/in-process output |
| `migration-reporting` | Synthesise plan, converted services, review briefs, and timeline into final report |

**Key outputs**:

- `service-analysis.json` — Service inventory with operation count, type complexity, and risk flags
- `service-modernisation-plan.json` — Sequenced plan with phases, effort, and manual review gates
- Generated REST controllers with routes, DTOs, and OpenAPI annotations
- Data-parity integration tests comparing original vs new implementations
- High-complexity review briefs with domain logic, risk analysis, and refactor guidance
- Cleaned project files with removed web references and updated using statements
- Migration report with completion summary and next-step checklist

**Risk mitigation**:

- High-complexity services are **never silently converted**; instead, a structured review brief with risk analysis and recommended refactor approach is produced
- All converted services include integration tests validating data-parity between original and new implementations
- Project cleanup removes dangling references and orphaned code

**Sequencing example** (Service A + Service B) :

- **Phase 1**: Service B — low‑complexity analysis and initial generation (lane 1)
- **Phase 2**: Service B — medium‑complexity review and refactoring (lane 2); Service A analysis begins (lane 1)
- **Phase 3**: Service A — API/controller generation; Service B — high‑complexity review gates with manual refactoring
- **Phase 4**: Integration testing and production deployment

---

### Azure Infrastructure Agent

**Entry point**: `.github/agents/azure-infra.agent.md`

Orchestrates the full Azure infrastructure provisioning workflow for .NET Framework enterprise applications migrating to Azure App Service. Runs a three-phase pipeline — analyse → plan → implement — handing off between three specialised sub-agents.

**Sub-agents**:

| Agent | Entry point | Purpose |
|-------|-------------|---------|
| Azure Infra Analyser | `.github/agents/azure-infra-analyser.agent.md` | Analyses the codebase and produces `infra-analysis.json` and `infra-analysis-summary.md` |
| Azure Infra Planner | `.github/agents/azure-infra-planner.agent.md` | Interviews the user and produces a zero-ambiguity `infra-plan.json` with all decisions recorded |
| Azure Infra Implementer | `.github/agents/azure-infra-implementer.agent.md` | Generates Bicep modules, per-environment parameter files, and CI/CD pipeline YAML |

**Key outputs**:

- `infra-analysis.json` and `infra-analysis-summary.md` — codebase infrastructure requirements
- `infra-plan.json` — approved provisioning plan with all decisions recorded
- Bicep modules under `infra/bicep/` — App Service Plan, Web App, Azure SQL, Key Vault, role assignments
- Per-environment parameter files (`params.dev.json`, `params.tst.json`, `params.uat.json`, `params.prd.json`)
- GitHub Actions CI/CD pipeline covering Dev → Test → UAT → Prod with approval gates

---

### .NET Framework Upgrade Agent

**Entry point**: `.github/agents/dotnet-framework-upgrade.agent.md`

Upgrades a .NET solution from any source framework version to a specified target version. Supports Classic-to-Classic paths (e.g. .NET Framework 4.0 → 4.8) and Classic-to-Modern paths (e.g. .NET Framework 4.0 → .NET 10). Handles project file format conversion, NuGet package resolution, build validation, and HTML report generation. Generic and reusable across any .NET application.

**Skills** (under `.github/skills/dotnet-framework-upgrade/`):

| Skill | Purpose |
|-------|---------|
| `upgrade-path-analysis` | Classify upgrade path type, inventory projects, identify high-risk items, produce upgrade plan |
| `framework-upgrade` | Apply framework version changes to project files and configuration |
| `nuget-package-upgrade` | Resolve and apply compatible NuGet package versions for the target framework |
| `build-validation` | Restore packages and build; iterate until zero errors |
| `upgrade-report-generator` | Produce the styled HTML upgrade report from all skill outputs |

**Key outputs**:

- `upgrade-report-<YYYY-MM-DD>.html` — self-contained styled HTML upgrade report
- `build-output.log` — raw build tool output
- `upgrade-path-analysis-report.json` — risk matrix, project inventory, and upgrade plan

> **When to use `dotnet-framework-upgrade` vs `dotnet-upgrade`**: Use this agent for a **single solution** that includes classic .NET Framework projects (WebForms, VB.NET, `packages.config`, `web.config`, WCF/ASMX). Use [`dotnet-upgrade`](#net-upgrade-agent) for **multiple SDK-style solutions** requiring batched execution, git branching, revert-on-failure, and Azure Functions support.

---

### .NET Test Automation and Quality Agent

**Entry point**: `.github/agents/dotnet-test-automation-and-quality-agent.md`

An expert C#/.NET testing and quality assurance agent. Writes clean, well-designed, and maintainable test code following .NET conventions and testing best practices. Applies SOLID principles, covers security, and supports TDD/BDD workflows.

**Skills** (under `.github/skills/dotnet-test-automation-and-quality/`):

| Skill | Purpose |
|-------|---------|
| `csharp-xunit` | Generate xUnit tests for C# projects with Moq and FluentAssertions |
| `csharp-nunit` | Generate NUnit tests for C# projects |
| `vbnet-xunit` | Generate xUnit tests for VB.NET projects |
| `playwright-explore-website` | Explore a website using Playwright MCP to identify key user flows before writing tests |
| `playwright-generate-test` | Generate well-structured Playwright tests in TypeScript based on explored flows |

---

### Playwright Tester Agent

**Entry point**: `.github/agents/playwright-tester-agent.md`

Explores websites using the Playwright MCP, generates well-structured Playwright tests in TypeScript, executes and refines them until all pass reliably, and documents tested functionalities.

**Modes**:

- **Website Exploration** — Navigate to the site, take a page snapshot, and identify key user flows before writing any code.
- **Test Improvements** — Use Playwright MCP to view the live page snapshot and identify correct locators for existing tests.
- **Test Generation** — Generate Playwright tests in TypeScript using role-based locators and web-first assertions based on explored flows.
- **Test Execution & Refinement** — Run tests, diagnose failures, and iterate until all pass reliably.
- **Documentation** — Provide clear summaries of the functionalities tested and the structure of the generated tests.

---

### E2E Baseline Orchestrator

**Entry point**: `.github/agents/e2e-baseline-orchestrator.agent.md`

Generates a Playwright E2E behavioural baseline test suite for a pre-migration Web Forms application. Performs static analysis of `.aspx` pages and all associated assets (VB/CS code-behinds, JavaScript, CSS, user controls), generates a fully self-contained C# NUnit Playwright test project (selector registry + page objects + test specs). Supports two execution modes: "static-only" (generates the test project from static code analysis alone — no running app or .NET SDK required) and "live-run" (also executes the suite against the deployed application to produce a signed-off baseline).

**Sub-agents**:

| Agent | Entry point | Purpose |
|-------|-------------|---------|
| E2E Baseline Page Discovery | `e2e-baseline-page-discovery.agent.md` | Discover all `.aspx` pages and extract metadata |
| E2E Baseline Selector Extractor | `e2e-baseline-selector-extractor.agent.md` | Extract selectors from pages and user controls |
| E2E Baseline Scenario Synthesiser | `e2e-baseline-scenario-synthesiser.agent.md` | Generate test scenarios from page analysis |
| E2E Baseline Test Generator | `e2e-baseline-test-generator.agent.md` | Generate C# NUnit Playwright test code |
| E2E Baseline Runner | `e2e-baseline-runner.agent.md` | Execute the generated test suite |
| E2E Baseline Validator | `e2e-baseline-validator.agent.md` | Validate test results and produce baseline report |

**Key outputs**:

- `docs/e2e-baseline/e2e-baseline.config.json` — configuration file
- C# NUnit Playwright test project with page objects and test specs
- Selector registry and test execution reports
- Signed-off baseline for pre-migration application behaviour

---

### Windows Service to Lambda Agent

**Entry point**: `.github/agents/windows-service-to-lambda.agent.md`

Migrates scheduled and event-driven .NET Framework 4.x Windows Service executables to AWS Lambda serverless functions. Reads existing service source code, generates equivalent Lambda handlers in C# (.NET 10 isolated worker), produces Terraform HCL or CloudFormation YAML for all supporting infrastructure, and outputs integration test stubs with mocked AWS SDK clients. Generic and reusable — not tied to any specific application name or business domain.

**Target triggers**: EventBridge Scheduler, SQS Queue, S3 Event Notifications

**Key outputs**:

- Lambda function code in C# (.NET 10)
- Terraform HCL or CloudFormation YAML for Lambda, EventBridge, SQS, DLQ, RDS Proxy
- Integration test stubs with mocked AWS SDK clients
- Migration report documenting refactored patterns

---