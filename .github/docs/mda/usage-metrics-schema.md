# Usage-metrics feed (GitHub user-level schema, extended)

`python .github/scripts/mda.py metrics` (also written by `report`) emits NDJSON to `docs/mda/<story>/usage-metrics.ndjson`: **one record per day + user + story**, shaped like GitHub's Copilot usage-metrics [user-level schema](https://docs.github.com/en/copilot/reference/copilot-usage-metrics/example-schema) so the same Power BI / Excel model can union GitHub's feed with ours on `day` + `user_login`.

| Field | Source here |
|---|---|
| `day`, `user_login` | local date of the interval; confirmed account (spec s3.4) |
| `user_initiated_interaction_count` | agent turns (prompt -> agentStop) that day |
| `used_cli` / `used_agent` | always true; other `used_*` false |
| `totals_by_cli` | `prompt_count`, `request_count`, `session_count`, `token_usage{prompt_tokens_sum (estimated), output_tokens_sum (null), avg_tokens_per_request}` |
| `totals_by_custom_agent` | sub-agent invocations (from subagentStart/Stop) |
| `totals_by_slash_cmd` | stage commands typed (`/plan`, `/build`, ...) |
| `distinct_*_use_count` | agents / slash commands computed; skill / MCP / plugin = null (not observable) |
| `loc_*`, `code_*_activity_count`, `ai_credits_used`, `user_id` | **null** - hooks cannot measure them; `ai_credits_used` belongs to GitHub's own developer-level feed (`mda.py usage`) |

## Extensions (not in GitHub's schema)
- `totals_by_stage[]`: `{cycle, stage, phase, trigger, interaction_count, ai_seconds, approval_seconds, manual_seconds, prompt_tokens_sum}` - follows GitHub's `totals_by_*` convention.
- `mda{}`: `schema` (`mda-user-story-day/1`), `project`, `story_id`, `cycle_current`, `sprint`, `active_seconds` (+ by phase: dev / qa-authoring / qa-execution), `capped_intervals`, `tokens_estimated: true`, and `complexity{model_version, calibrated, tier, score, counts, weights, traditional_days}` (raw factors kept for recalibration).

## Rules
- Null means "not measured", never a fake zero.
- Token figures are estimates (prompt chars / 4); do not compare them to GitHub's measured `token_usage` without that caveat.
- QA manual execution appears only under `phase: qa-execution` (no AI-efficiency claim).
- Uncalibrated complexity is flagged in `mda.complexity.calibrated`; keep it out of client-facing views until true.
