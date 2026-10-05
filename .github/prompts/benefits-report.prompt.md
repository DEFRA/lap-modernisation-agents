---
mode: migration-delivery
description: AI Productivity (AI Efficiency) report for a project and optional date range - local preview, or point to the ADO pipeline for the real Excel
argument-hint: "<ADO project> [from YYYY-MM-DD] [to YYYY-MM-DD]"
---
Delegate to `reporting-agent`:

1. `python .github/scripts/mda.py benefits --project "<project>" [--from <date>] [--to <date>] --xlsx --print` for a **local preview only**. It sees only stories cached on this machine, so say so plainly; never present it as the final number if more than one developer worked the project.
2. For the real, all-developer Excel, tell the developer to run the **mda-ai-efficiency-report** pipeline (`.github/pipelines/mda-ai-efficiency-report.yml`) in that project's Azure DevOps, with the optional From/To dates (blank = all data). You cannot trigger it yourself.

State which cells are measured, which are NEEDS INPUT (no traditional estimate for the phase), and the flags printed under the table (LLM-estimated traditional effort, unconfirmed estimates, missing token data, idle gaps excluded). Never fill a gap with a guess. Detail: `.github/docs/mda/benefits-report.md`.
