# Build progress (spec §14) — named gaps are visible, never silent

Legend: ✅ built and covered by unit tests · 🟡 built, **not verified against a live system** · ⬜ not built (named gap)

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Setup: blocking capture, PAT expiry check, account confirmation (§3) | ✅ / 🟡 | Blocking + gating tested. Account detection reads `~/.copilot/config.json` and `gh auth status` — format assumptions unverified on your CLI version. PAT expiry is developer-supplied (not discoverable) |
| 2 | Local cache, every-N-prompt check, heartbeat, recovery (§3.2) | ✅ (stub ADO) / 🟡 | Tested with an in-memory ADO transport. Heartbeat is opportunistic on hook events (no daemon) |
| 3 | Subagent reuse check (§2) | ✅ | [reuse-check.md](reuse-check.md) |
| 4 | Requirements / Discovery / Architecture commands (§4) | ✅ | Prompts + agents + skills |
| 5 | Approval gates via hooks (§5) | 🟡 **blocks a real hook-enforced test** | Logic tested against synthetic hook calls only. **Not verified that Copilot CLI discovers `.github/hooks/mda-hooks.json` at all**, its event names, or the `agentStop` block/continue output shape |
| 5a | Fallback for runtimes with no hook layer (e.g. a `.agent.md` selected from the VS Code Copilot Chat dropdown, which has no equivalent hook system) | ✅ | `mda.py turn start/end` and `gate-manual approve/request-changes --verbatim` self-drive timing and gate recording; a `hooked` flag on the session prevents double-counting if a real hook is also present. Weaker trust model than hooks — see [runtimes.md](runtimes.md) |
| 6 | State machine + cycles (§6) | ✅ | |
| 7 | Effort formula + hook wiring (§7.1–7.4) | ✅ / 🟡 | Formula tested; payload field names lenient but unverified |
| 8 | Per-developer usage sync (§7.5) | 🟡 | `gh api …/premium_request/usage`; endpoint/response shape not exercised live. Runs at session start when last snapshot > 24h |
| 9 | Complexity scoring, raw factors stored (§8.1–8.3) | ✅ | |
| 10 | 40% efficiency baseline in reporting (§8.4) | ✅ | Shown as anchor, measured vs assumed |
| 11 | Complexity calibration (§8.3) | 🟡 | `complexity calibrate` tool built and tested on synthetic data; **needs 10–15 real completed stories** — model stays UNCALIBRATED until then |
| 12 | Build, Quality gates, self-heal with cap (§4) | ✅ / 🟡 | Cap enforced by hook; cap value not yet fixed by governance |
| 13 | Commit & PR packaging, template parsing (§4) | 🟡 | Agent instructions only; no code, not exercised |
| 14 | QA authoring + manual execution split (§9) | ✅ | Separate phase, separate report line |
| 15 | Post-PR fix commands, developer-only, no SSH (§10) | ✅ | |
| 16 | SonarCloud public API + fallback (§10.1) | ✅ (stubbed) / 🟡 | Fallback tested; anonymous rate limits unverified. Official Sonar MCP not wired (optional) |
| 17 | ADO structured fields + Wiki (§11) | 🟡 | Tested against stub; needs real ADO run. Custom fields must be created manually ([ado-setup.md](ado-setup.md)) |
| 18 | Native ADO dashboards (§12.1) | ⬜ | Queries and design documented in [dashboards.md](dashboards.md); dashboards themselves must be built in ADO |
| 19 | Power BI dashboard (§12.2) | ⬜ | Deliberately deferred |
| 20 | Pipeline: Excel export + Wiki append (§13) | 🟡 | Data shaping tested with pandas; pipeline run and wiki PUT/ETag unverified |

## Open governance items
- **Complexity weights/bands** are uncalibrated — no client-facing use until calibration is accepted.
- **Self-heal max retries** — default 3 is a placeholder (`gates.self_heal_max_retries`).
- **`sessionId` reliability** across hook types — code falls back to env then a workspace pointer and flags `session_id_unreliable`; verify.
- **Idle caps** (not in the spec): the literal formula `approval − last response` would count an overnight gap if a developer approves next morning. Gaps and turns over 120 min are truncated and flagged. Decide the cap.
- **Story-level tokens** are estimates from prompt size; hooks don't expose model token counts. Developer-level usage comes from billing data.
- **Power BI licensing** approval.
- **SonarCloud anonymous rate limits** under real volume.
