"""Approval-gate mechanics (spec s5): human-only approval detection and tool gating.

Approval is only ever recorded by the userPromptSubmitted hook, which sees what the
developer actually typed. The agent has no CLI verb that approves, so it cannot approve
its own work.
"""
from __future__ import annotations

import re

APPROVE_RE = re.compile(r"^\s*/?(approve|approved|lgtm)\b[\s:,-]*(.*)$", re.I | re.S)
CHANGES_RE = re.compile(r"^\s*/?(request[- ]changes|changes[- ]requested|reject)\b[\s:,-]*(.*)$", re.I | re.S)

READ_ONLY_TOOLS = {"view", "read", "grep", "glob", "search", "list", "ls", "codebase", "fetch",
                   "web_fetch", "todo", "todos", "report_intent", "think", "thinking", "ask_user",
                   "task", "agent"}
WRITE_TOOLS = {"edit", "create", "write", "str_replace", "str_replace_editor", "apply_patch",
               "multi_edit", "editfiles", "edit/editfiles"}
SHELL_TOOLS = {"bash", "powershell", "shell", "terminal", "runcommands", "execute", "run_in_terminal"}
SAFE_SHELL = re.compile(
    r"^\s*(git\s+(status|diff|log|show|branch|rev-parse|remote)|ls|dir|cat|type|pwd|echo|"
    r"python3?\s+\S*mda\.py|py\s+\S*mda\.py)\b", re.I)


def classify_prompt(prompt: str):
    """Returns ('approve'|'changes'|None, text)."""
    if not prompt:
        return None, ""
    m = CHANGES_RE.match(prompt)
    if m:
        return "changes", m.group(2).strip()
    m = APPROVE_RE.match(prompt)
    if m:
        return "approve", m.group(2).strip()
    return None, ""


def _tool_command(args) -> str:
    if isinstance(args, str):
        return args
    if isinstance(args, dict):
        for k in ("command", "cmd", "script", "input"):
            if isinstance(args.get(k), str):
                return args[k]
    return ""


def tool_decision(tool_name: str, tool_args, *, setup_missing: list, awaiting: str,
                  escalated: bool, bound: bool) -> dict:
    """Returns {'allow': bool, 'reason': str}. Read-only tools and mda.py are always allowed."""
    name = (tool_name or "").lower()
    if not bound or name in READ_ONLY_TOOLS:
        return {"allow": True, "reason": ""}
    is_write = name in WRITE_TOOLS
    is_shell = name in SHELL_TOOLS
    if not (is_write or is_shell):
        return {"allow": True, "reason": ""}
    cmd = _tool_command(tool_args)
    safe = is_shell and bool(SAFE_SHELL.match(cmd))
    if safe:
        return {"allow": True, "reason": ""}
    if setup_missing:
        return {"allow": False, "reason": "MDA setup incomplete - ask the developer for: "
                + "; ".join(setup_missing) + ". No pipeline work until captured."}
    if awaiting:
        return {"allow": False, "reason": f"Stage '{awaiting}' is awaiting developer approval. "
                "Do not make changes; present the result and wait for the developer to reply "
                "'approve' or 'request changes: <text>'."}
    if escalated:
        return {"allow": False, "reason": "Self-heal retry cap reached. Stop, summarise the "
                "failures for the developer and ask how to proceed."}
    return {"allow": True, "reason": ""}
