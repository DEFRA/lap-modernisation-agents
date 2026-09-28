"""GitHub/Copilot account resolution (s3.4) and ADO PAT prerequisite check (s3.3).

The PAT is only ever read from the environment and is never written to disk or logged.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

from .core import load_config, utcnow


def _run(cmd, timeout=15):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def copilot_cli_account() -> dict:
    """The identity the Copilot CLI session itself is authenticated as (NOT VS Code, NOT gh)."""
    home = Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot")
    for name in ("config.json", "settings.json"):
        p = home / name
        if not p.exists():
            continue
        try:
            text = "\n".join(l for l in p.read_text(encoding="utf-8-sig").splitlines()
                             if not l.lstrip().startswith("//"))
            cfg = json.loads(text)
        except (OSError, ValueError):
            continue
        last = cfg.get("last_logged_in_user") or cfg.get("lastLoggedInUser")
        users = cfg.get("logged_in_users") or cfg.get("loggedInUsers") or []
        if isinstance(last, dict) and last.get("login"):
            return {"login": last["login"], "host": last.get("host", "github.com"),
                    "source": str(p), "all_cli_users": [u.get("login") for u in users if isinstance(u, dict)]}
        if users and isinstance(users[0], dict):
            return {"login": users[0].get("login"), "host": users[0].get("host", "github.com"),
                    "source": str(p), "all_cli_users": [u.get("login") for u in users if isinstance(u, dict)]}
    return {"login": None, "source": None,
            "note": "Copilot CLI account not found in ~/.copilot config; ask the developer."}


def gh_accounts() -> list:
    rc, out = _run(["gh", "auth", "status"])
    if rc == 127:
        return []
    accts, cur = [], None
    for line in out.splitlines():
        m = re.search(r"Logged in to (\S+) (?:account|as) (\S+)", line)
        if m:
            cur = {"host": m.group(1), "login": m.group(2).strip("()"), "active": False}
            accts.append(cur)
        elif cur and "Active account:" in line:
            cur["active"] = "true" in line.lower()
    return accts


def git_user() -> dict:
    return {"name": _run(["git", "config", "user.name"])[1].strip(),
            "email": _run(["git", "config", "user.email"])[1].strip()}


def detect_accounts() -> dict:
    cli = copilot_cli_account()
    gh = gh_accounts()
    cands = []
    for login in [cli.get("login")] + [a["login"] for a in gh] + list(cli.get("all_cli_users") or []):
        if login and login not in cands:
            cands.append(login)
    diverge = bool(cli.get("login") and gh and not any(a["active"] and a["login"] == cli["login"] for a in gh))
    return {"copilot_cli": cli, "gh_accounts": gh, "git_user": git_user(), "candidates": cands,
            "accounts_diverge": diverge,
            "prompt_user": "Ask the developer which account prompts should be attributed to. "
                           "Do not auto-select."}


def prerequisites() -> dict:
    return {"git": _run(["git", "--version"])[0] == 0, "gh": _run(["gh", "--version"])[0] == 0,
            "gh_authenticated": bool(gh_accounts())}


# ------------------------------------------------------------------ PAT

def pat_from_env():
    return os.environ.get("MDA_ADO_PAT") or os.environ.get("AZURE_DEVOPS_EXT_PAT") \
        or os.environ.get("SYSTEM_ACCESSTOKEN")


def pat_expiry_from_env():
    v = os.environ.get("MDA_ADO_PAT_EXPIRY")
    if not v:
        cfg = load_config()
        v = cfg.get("pat", {}).get("expiry")
    return v


def check_pat(client=None, today: dt.date = None) -> dict:
    """blocked = missing/expired/rejected; warn = expires within warn_days; ok otherwise.

    Expiry is not discoverable through the PAT itself, so the developer supplies
    MDA_ADO_PAT_EXPIRY (YYYY-MM-DD). Missing expiry is reported as a warning to fix."""
    cfg = load_config()
    today = today or utcnow().date()
    res = {"status": "ok", "messages": [], "scopes": {}}
    if not pat_from_env():
        return {"status": "blocked", "messages": [
            "No ADO PAT found. Set MDA_ADO_PAT (scopes: Work Items read & write, Wiki read & write, "
            "Analytics read) and MDA_ADO_PAT_EXPIRY=YYYY-MM-DD, then re-run."], "scopes": {}}
    if not cfg["ado"]["org_url"]:
        return {"status": "blocked", "messages": [
            "ADO org URL not configured. Set MDA_ADO_ORG_URL or ado.org_url in "
            ".mda/config.local.json."], "scopes": {}}
    exp = pat_expiry_from_env()
    if exp:
        try:
            d = dt.date.fromisoformat(exp)
            left = (d - today).days
            res["days_left"] = left
            if left < 0:
                return {"status": "blocked", "days_left": left, "scopes": {}, "messages": [
                    f"PAT expired on {exp}. Ask the developer for a new PAT."]}
            if left <= cfg["pat"]["warn_days"]:
                res["status"] = "warn"
                res["messages"].append(f"PAT expires in {left} day(s) ({exp}). Proceeding; "
                                       "will re-check on next session start.")
        except ValueError:
            res["status"] = "warn"
            res["messages"].append(f"MDA_ADO_PAT_EXPIRY '{exp}' is not YYYY-MM-DD.")
    else:
        res["status"] = "warn"
        res["messages"].append("MDA_ADO_PAT_EXPIRY not set; expiry cannot be checked.")
    if client is not None:
        res["scopes"] = client.probe_scopes()
        bad = [k for k, v in res["scopes"].items() if v is False]
        if bad:
            return {**res, "status": "blocked", "messages": res["messages"] + [
                f"PAT lacks or was rejected for: {', '.join(bad)}."]}
    return res
