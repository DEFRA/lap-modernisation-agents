# Real token usage: Copilot OpenTelemetry setup

Copilot's hooks do not carry token counts. What does: the **OpenTelemetry (OTel) export** built into both Copilot Chat in VS Code and the Copilot CLI. Each LLM call (`chat` span) and each agent run (`invoke_agent` span) records `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, the model, start/end time, `gen_ai.conversation.id` and `gen_ai.agent.name` (sub-agents are nested `invoke_agent` spans). Source: the [Copilot Chat monitoring doc](https://github.com/microsoft/vscode-copilot-chat/blob/main/docs/monitoring/agent_monitoring.md).

The agent imports a **local JSON-lines file**, so no collector or server is needed, and **prompt/response content is not captured** (`captureContent` stays off), so no code or prompt text is in the file.

## Turn it on

**VS Code (Copilot Chat)**, in the workspace `.vscode/settings.json` (or user settings):

```json
{
  "github.copilot.chat.otel.enabled": true,
  "github.copilot.chat.otel.exporterType": "file",
  "github.copilot.chat.otel.outfile": "${workspaceFolder}/.mda/otel/copilot.jsonl",
  "github.copilot.chat.otel.captureContent": false
}
```
If `${workspaceFolder}` is not expanded by your version, use the absolute path. The file must be at the path in `otel.file` (default `.mda/otel/copilot.jsonl`, relative to the repo root; `.mda/` is git-ignored).

**Copilot CLI (terminal)**, environment variables before starting `copilot`:

```
COPILOT_OTEL_ENABLED=true
COPILOT_OTEL_FILE_EXPORTER_PATH=<repo>/.mda/otel/copilot.jsonl
```
(The CLI runtime documents only the HTTP exporter for network export; the file path variable is documented for "all signals". Verify with the check below.)

If your organisation blocks these settings by policy, tokens stay UNAVAILABLE; the report says so.

## Verify (do this once per install: it is the proof the numbers can be trusted)

1. Run one chat turn in the workspace.
2. `python .github/scripts/mda.py otel check`

It reports whether the file exists, how many spans were read, how many `chat` spans carry tokens, the agents, models and conversation ids seen, which token/cache/reasoning attributes exist, and the total tokens. **The reader accepts OTLP-JSON, OTel-JS console-style and flat span lines, but the exact line format of the file exporter has not been confirmed against a live install in this repo.** If `check` shows no chat spans, send the first two lines of the file (they contain no prompt text) and the reader will be adjusted. Do not trust a token number until `check` passes on your machine.

## How it flows into the numbers

- `mda.py turn end`, `mda.py report`, and the session hooks import new spans (idempotent; late spans update the same entry).
- Chat spans are rolled up to one `usage` entry per user turn, per agent, per model. A parent `invoke_agent` span's own totals are never added on top of its children.
- Each entry is booked to the stage window that was open when the call started (start, resume, changes, submit... until approve). Calls outside any window go to `unassigned`.
- Optional: `otel.import_turn_time: true` also takes AI turn time from the root `invoke_agent` spans (useful in VS Code Chat, where there are no hooks). It never adds a turn that a hook or `turn start/end` already timed.
- Real tokens (`tokens_in/out`, `token_source: otel`) are kept apart from the prompt-size estimate (`tokens_est`), which is never added to them.

## Not covered
- Cached or reasoning tokens: the documentation lists only input and output; `otel check` lists any extra attributes your version emits.
- Premium-request billing is a different, per-developer figure from GitHub's billing API (`mda.py usage`).
- A developer who has OTel off for a turn leaves a gap; the report counts rows by token source and flags it.
