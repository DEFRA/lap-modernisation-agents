# Environment setup (PAT and ADO connection) — Windows and macOS

One-off, per developer machine. Never commit these values; nothing here is written to a file the agent tracks.

## 1. Create the PAT in Azure DevOps

Azure DevOps → user settings (top right) → **Personal access tokens** → **New Token**.

- Organization: the org you'll point `MDA_ADO_ORG_URL` at.
- Scopes (custom, not "Full access"):
  - **Work Items** → Read & write
  - **Wiki** → Read & write
  - **Analytics** → Read
- Expiration: note the exact date — you'll set it below too, since ADO gives no API to read a PAT's own expiry.

Copy the token now; ADO shows it once.

## 2. Set the environment variables

| Variable | Value | Required |
|---|---|---|
| `MDA_ADO_PAT` | the token from step 1 | yes |
| `MDA_ADO_PAT_EXPIRY` | `YYYY-MM-DD`, matching the PAT's expiry | yes (a missing value only warns, but do set it) |
| `MDA_ADO_ORG_URL` | `https://dev.azure.com/<org>` | yes |
| `MDA_ADO_PROJECT` | the ADO project name | yes |
| `MDA_SESSION_ID` | any stable string | no — Copilot CLI normally supplies this; only set it if `mda.py session` reports `session_id_unreliable` |

### Windows (PowerShell)

Session-only (cleared when you close the terminal):

```powershell
$env:MDA_ADO_PAT = "xxxxxxxxxxxxxxxxxxxxxxxx"
$env:MDA_ADO_PAT_EXPIRY = "2026-12-31"
$env:MDA_ADO_ORG_URL = "https://dev.azure.com/defra"
$env:MDA_ADO_PROJECT = "LAP-Civica"
```

Persist across terminals/reboots (current user only — do **not** use `/M` machine-wide, that exposes the PAT to every user on the box):

```powershell
setx MDA_ADO_PAT "xxxxxxxxxxxxxxxxxxxxxxxx"
setx MDA_ADO_PAT_EXPIRY "2026-12-31"
setx MDA_ADO_ORG_URL "https://dev.azure.com/defra"
setx MDA_ADO_PROJECT "LAP-Civica"
```

`setx` only takes effect in **new** terminal windows opened after you run it — close and reopen VS Code / the terminal before testing.

Check it stuck:

```powershell
[Environment]::GetEnvironmentVariable("MDA_ADO_PAT", "User")   # prints the value if set
```

Remove it later:

```powershell
[Environment]::SetEnvironmentVariable("MDA_ADO_PAT", $null, "User")
```

### macOS (zsh, the default shell since Catalina)

Session-only:

```bash
export MDA_ADO_PAT="xxxxxxxxxxxxxxxxxxxxxxxx"
export MDA_ADO_PAT_EXPIRY="2026-12-31"
export MDA_ADO_ORG_URL="https://dev.azure.com/defra"
export MDA_ADO_PROJECT="LAP-Civica"
```

Persist across terminals (appends to your shell profile — check `echo $SHELL` first; use `~/.bash_profile` instead of `~/.zshrc` if it prints `/bin/bash`):

```bash
cat >> ~/.zshrc <<'EOF'
export MDA_ADO_PAT="xxxxxxxxxxxxxxxxxxxxxxxx"
export MDA_ADO_PAT_EXPIRY="2026-12-31"
export MDA_ADO_ORG_URL="https://dev.azure.com/defra"
export MDA_ADO_PROJECT="LAP-Civica"
EOF
source ~/.zshrc
```

Prefer not to put a secret in a plaintext dotfile? Use the macOS Keychain and read it at shell start instead of hardcoding it:

```bash
security add-generic-password -a "$USER" -s MDA_ADO_PAT -w "xxxxxxxxxxxxxxxxxxxxxxxx"
# then in ~/.zshrc:
export MDA_ADO_PAT="$(security find-generic-password -a "$USER" -s MDA_ADO_PAT -w)"
```

Remove it later: `security delete-generic-password -s MDA_ADO_PAT`.

## 3. Verify (either OS)

```
python .github/scripts/mda.py ado check
```

- `"status": "ok"` or `"warn"` (PAT expiring soon) → good to go.
- `"status": "blocked"` → read `messages`; usually a missing/expired PAT, a missing org URL, or a scope the PAT doesn't have.

## 4. `git` and `gh` (also required — spec §3.4)

Both must be installed and `gh` authenticated, since the agent resolves and confirms the GitHub/Copilot account from them, not from VS Code's own sign-in.

- Windows: `winget install --id GitHub.cli`, then `gh auth login`.
- macOS: `brew install gh`, then `gh auth login`.

Check: `python .github/scripts/mda.py setup prereqs`.

## 5. Optional: sprint dates for reporting

Not an environment variable — create `.mda/config.local.json` (git-ignored) in the repo root:

```json
{ "sprints": [{ "name": "Sprint 12", "start": "2026-09-01", "end": "2026-09-14" }] }
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ado_not_configured` on every sync | one of the four required env vars is empty in *this* terminal session — `setx`/profile edits need a fresh terminal |
| PAT status `blocked`, scope reported false | the field wasn't granted at PAT creation; make a new PAT rather than trying to edit scopes |
| Works in one terminal, not another | you set it session-only (`$env:`/`export`), not persisted — use `setx` or the profile file |
| `setup accounts` shows no candidates | `gh auth login` not run, or `~/.copilot` config not found — this only affects account **display**, not the PAT check |
