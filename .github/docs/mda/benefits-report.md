# AI Productivity (AI Efficiency) report

The Excel the programme asked for: Application Context, Benefits (**Effort saving, Time saving, Cost saving, Automated completion**) and a **Delivery Comparison** by phase (Discovery, Design, Build, Test, Transition to Live, Support): Traditional PD vs AI PD, Traditional days vs AI days, Automation %, Evidence. Cost cells are intentionally blank.

## Two ways to get it, same code

| | `mda.py benefits --project X --xlsx` | The `mda-ai-efficiency-report` ADO pipeline |
|---|---|---|
| Whose data | Stories cached on **this machine** only | **Every developer's** synced records in that ADO project |
| Use for | A quick look | The real number |
| Output | `docs/mda/_programme/<project>/ai-efficiency-preview.{md,json,xlsx}` | `.xlsx` build artifact (+ optional wiki summary) |

If more than one developer worked the project, the local preview understates it. Say so whenever it is shown.

## Date range
Pipeline parameters **From date** and **To date** (YYYY-MM-DD, inclusive, both optional; **blank = all data**; From after To is rejected). The local preview takes `--from` / `--to`. Rows are filtered by the **work date** (the day the work happened), not the day the record was written. Optional: story IDs, application name and technology stack for the header.

## How each number is built

- **PD (person-days)** = active hours / hours-per-day (7.5). Active hours = AI turn time + developer review time before each approval + manual time. Idle gaps (an approval that took more than 2 hours) are **excluded**, not guessed.
- **AI days** = the number of distinct calendar dates on which work in that phase was actually measured (two developers on the same date count once). A weekend gap does not create days.
- **Traditional PD** = the story's **LLM-estimated** person-days for that phase (proposed at `/plan` with a reason per phase, adjustable and confirmed by the developer). For a date range the story's figure is pro-rated by the share of its measured effort that falls inside the range (full range = full estimate). **Traditional days = traditional PD** (one person-day per day); stated on the sheet.
- **Effort saving** = 1 - AI PD / Traditional PD. **Time saving** = 1 - AI days / Traditional days. Both over the phases that have both figures.
- **Automated completion** = measured AI processing time / (AI + review + manual time). Our definition; change `DEFINITIONS` in `benefits.py` if the programme means something else.
- **Like for like:** a story contributes to a phase only if it has a traditional figure for that phase. Its effort in other phases is listed on the Details sheet ("Excluded"), never silently mixed in.
- Stage to phase: requirements + discovery -> Discovery; plan -> Design; build + pr -> Build; quality + QA authoring + QA execution -> Test; Transition to Live and Support come from `/log-manual` entries.

## The traditional estimate (what is real and what is not)
There is no rate card. The traditional figure is the LLM's judgement, recorded phase by phase with a one-sentence reason, shown to the developer at the plan gate, and labelled **LLM-estimated, unvalidated** in every output, whether or not the developer confirmed it. Confirming means "I accept this as the baseline", not "this is measured". Transition to Live and Support are entered by the developer (`mda.py estimate set --phase transition_to_live ...`). The credibility of the saving percentages rests on this baseline: if the programme later has real historical effort per factor, a rate card can be added back without changing the report.

## Honest limits
- Traditional effort is an **LLM estimate** confirmed by a developer, not a measurement. The sheet's flags say so, and when an estimate is unconfirmed.
- Token columns are real only for turns where Copilot's OpenTelemetry export was on (`otel-setup.md`); otherwise they are blank/estimate and flagged.
- Cost is not produced.
- Anything without a traditional estimate shows NEEDS INPUT; nothing is filled with a guess.

## Workbook layout
Sheet 1 mirrors the programme template (title, Application Context, Benefits, Delivery Comparison with live formulas for totals and percentages). Sheet 2 "Details": date range, stories, data-quality flags, tokens by stage and by agent (input/output, source mix), excluded stories, definitions. Sheet 3 "Effort Rows": the per-developer, per-day rows behind the numbers.
