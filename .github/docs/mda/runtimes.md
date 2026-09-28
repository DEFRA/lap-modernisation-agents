# Two runtimes: GitHub Copilot CLI vs. VS Code Copilot Chat

The agent files (`.agent.md`) work unchanged in both places. **What differs is how much of the pipeline is enforced by something other than the model following its own instructions.**

## Copilot CLI — hook-enforced (the stronger mode)

Run via the standalone `copilot` CLI tool. `.github/hooks/mda-hooks.json` wires ten events (`sessionStart`, `userPromptSubmitted`, `agentStop`, `subagentStart`/`Stop`, `permissionRequest`, `postToolUseFailure`, …) to `mda_hook.py`, which runs **outside the model's control**:

- AI-turn timing is captured automatically at prompt/stop boundaries.
- Approval is read from the developer's raw prompt text by the hook, independently of the LLM — the agent cannot fabricate an approval because it never sees or produces the record; the hook does.
- Edit/shell tools are denied by the hook while a stage is `awaiting_approval`.
- A run of consecutive tool failures is counted and capped by the hook, not by the model choosing to stop.

**Status: the hook wiring itself is unverified against a real Copilot CLI install** (see `build-checklist.md` item 5) — the logic is unit-tested against synthetic hook payloads only.

## VS Code Copilot Chat, agent selected from the dropdown — instruction-enforced

`.agent.md` files are VS Code's native custom-agent format, so the orchestrator and sub-agents load and run correctly here. **But VS Code custom agents have no equivalent hook layer** — per VS Code's own docs they are "system prompts with tool restrictions," not an event-driven system. VS Code does have its own hook feature, but it is Preview, opt-in (`chat.useHooks`), restricted to the "Local harness" (not the default session target Copilot Chat uses), and only documents one event (`PostToolUse`) — nothing equivalent to reading the developer's raw prompt or denying a tool call.

So in this mode there is **no external enforcer**. To still work, the orchestrator drives itself explicitly:

| Copilot CLI does automatically | VS Code Chat: the orchestrator calls |
|---|---|
| Time an AI turn | `mda.py turn start` at the top of its turn, `mda.py turn end` as its last action |
| Record your approval from the raw prompt | `mda.py gate approve --verbatim "<your exact reply>"` — **only** when your reply, quoted exactly, matches `approve` |
| Record "request changes" | `mda.py gate request-changes --verbatim "<your exact reply>"` |
| Deny edits while awaiting approval | Nothing denies it technically — the orchestrator's own rules say to stop and wait |

**The safeguard that does exist:** `gate approve`/`gate request-changes` re-derive the approve/changes verdict from the `--verbatim` text themselves (the same pattern match the hook uses) rather than trusting whatever the model claims. A vague or paraphrased reply ("looks fine to me") is rejected with `verbatim_does_not_match`; only an exact `approve` / `request changes: …` (case-insensitive, `/approve` also accepted) is recorded. This stops the model from calling something "close enough" to approval. **It does not stop the model from inventing text and passing it as `--verbatim`** — there is no independent witness to what you actually typed in this mode. That is the honest limit of instruction-enforcement: the agent's own `.agent.md` rules are explicit that it must pass your reply verbatim and never approve on its own judgment, but nothing outside the model checks that it complied.

**Both commands are no-ops on a hooked session** (`gate-manual`/`turn` check `session hooked`, from `mda.py session`, and skip immediately) so running under Copilot CLI never double-counts effort or double-records an approval even if the orchestrator calls them by mistake.

## How the orchestrator knows which mode it's in

`mda.py session` reports `"hooked": true/false`. It starts `false` and flips to `true` the moment any real hook event has ever fired for that session — there is nothing to configure. The orchestrator checks this once per session (see `migration-delivery.agent.md`) and behaves accordingly for the rest of it.

## Practical effect on the numbers

| | Copilot CLI | VS Code Chat |
|---|---|---|
| Effort timing | Automatic, hook-timed | Present, but only as accurate as the orchestrator remembering to call `turn start`/`turn end` every turn |
| Approval record | Independently witnessed | Pattern-checked, not independently witnessed |
| Tool gating while awaiting approval | Enforced | Instruction-only |
| Self-heal retry cap | Enforced | Instruction-only (the orchestrator is told to stop and ask; nothing stops it if it doesn't) |

If you need the harder guarantees (e.g. this feeds a client-facing effort claim), prefer running the pipeline through Copilot CLI once its hook wiring is verified. VS Code Chat is fine for day-to-day development and still produces the same reports and ADO records — just with a softer trust model.
