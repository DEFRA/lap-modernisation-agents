# Complexity model calibration (spec s8.3)

Status: **not yet calibrated** (`calibrated: false` in `.github/config/mda/complexity-model.json`).

## Method
1. Pick 10-15 completed migration stories with a trustworthy actual traditional effort (days, pre-AI or a reasoned equivalent).
2. Count the factors retroactively per story using the discovery skill's rules (`.github/skills/migration-delivery/discovery/SKILL.md`). Record in a CSV: `story_id, actual_traditional_days` plus one column per factor in `complexity-model.json` (14 now: `screen_simple, complex_form, business_function, validation_rule, internal_api_endpoint, external_integration, db_object, stored_procedure, ssis_package, wcf_asmx_service, report_template, background_job, identity_flow, test_scenario`).
3. `python .github/scripts/mda.py complexity calibrate --history history.csv` fits non-negative weights (NNLS) and proposes band edges from the 25/50/75th percentiles of actual days and fitted scores. Efficiency figures are carried over unchanged - they need pilot data (measured vs assumed appears in every report).
4. Review R-squared, MAPE and the proposed weights with the team; sanity-check outliers. Re-run with `--accept` to write the model and set `calibrated: true`.
5. Record the data set, date and reviewers here.

## History
| Date | Stories | R-squared | MAPE | Accepted by |
|---|---|---|---|---|
| - | - | - | - | - |
