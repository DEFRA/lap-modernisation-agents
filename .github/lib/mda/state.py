"""Story record, session record, stage state machine and cycles (spec s3.1, s5, s6)."""
from __future__ import annotations

import copy
import os
import uuid
from pathlib import Path

from .core import iso, read_json, repo_root, store_dir, write_json

STAGES = ["setup", "requirements", "discovery", "plan", "build", "quality", "pr",
          "qa_authoring", "qa_execution"]
PREREQ = {
    "requirements": [], "discovery": ["requirements"], "plan": ["discovery"],
    "build": ["plan"], "quality": ["build"], "pr": ["quality"],
    "qa_authoring": ["plan"], "qa_execution": ["pr", "qa_authoring"],
}
STATUSES = ("not_started", "in_progress", "awaiting_approval", "approved")
PHASE = {"qa_authoring": "qa-authoring", "qa_execution": "qa-execution",
         # manual-entry phases (no pipeline stage; logged with `mda.py manual log`)
         "transition_to_live": "transition_to_live", "support": "support",
         # turns that happen outside any stage/activity window; never counted as dev effort
         "unassigned": "unassigned"}
PHASES = ("dev", "qa-authoring", "qa-execution", "transition_to_live", "support", "unassigned")
MANUAL_STAGES = ("transition_to_live", "support")
# activity commands (no gate of their own) -> the stage whose effort they belong to
ACTIVITY_STAGE = {"research": "discovery", "db-analysis": "discovery", "unit-test": "quality",
                  "security-review": "quality", "document": "plan"}
TRIGGERS = ("pr-review", "sonar-recheck", "qa-defect", "dev-reopen")
# subagent (agent file name) -> stage it owns
SUBAGENT_STAGE = {
    "requirements-agent": "requirements", "legacy-analyst": "discovery",
    "target-architect": "plan", "build-engineer": "build",
    "quality-gate-agent": "quality", "release-packager": "pr",
    "qa-authoring-agent": "qa_authoring",
}


def phase_of(stage: str) -> str:
    return PHASE.get(stage, "dev")


def log_stage_event(story: dict, stage: str, event: str) -> None:
    """Append-only stage timeline (start/resume/changes/activity_start open a window; approve/wait/
    activity_end close it; submit keeps it open so review chat is still attributed to the stage).
    Used to attribute OpenTelemetry token usage to the stage that was active at the time."""
    story.setdefault("stage_events", []).append({"stage": stage, "event": event, "at": iso()})
    story["stage_events"] = story["stage_events"][-2000:]


def stage_at(story: dict, ts) -> str | None:
    """Stage whose window contains `ts` (a datetime), or None."""
    from .core import parse_ts
    cur = None
    for ev in sorted(story.get("stage_events", []), key=lambda e: e["at"]):
        if parse_ts(ev["at"]) > ts:
            break
        if ev["event"] in ("start", "resume", "changes", "activity_start"):
            cur = ev["stage"]
        elif ev["event"] in ("approve", "wait", "activity_end") and cur == ev["stage"]:
            cur = None
    return cur


def artifact_path(story_id, stage: str) -> Path:
    return repo_root() / "docs" / "mda" / str(story_id) / f"{stage}.md"


# ------------------------------------------------------------------ story

def _story_file(story_id) -> Path:
    return store_dir() / "stories" / f"story-{story_id}.json"


def new_story(project: str, story_id) -> dict:
    return {
        "schema": 1, "project": project, "story_id": str(story_id), "created": iso(),
        "setup": {"is_migration": None, "application": None, "tech_stack": None,
                  "paths": {"old": None, "new": None, "hld": None, "hlsa": None, "lld": None},
                  "account": {}, "pat": {}, "auto_continue": False},
        "cycle": 1, "complete": False, "closed": False, "current_trigger": None,
        "pr": {"raised": False, "url": None, "number": None},
        "stages": {s: {"status": "not_started"} for s in STAGES if s != "setup"},
        "cycle_history": [], "effort": [], "stage_events": [], "estimate": None,
        "complexity": {"counts": None, "result": None, "confirmed": False},
        "sync": {"revision": 0, "last_sync": None, "last_check": None, "dirty": True,
                 "prompt_count": 0, "row_hashes": {}},
        "anomalies": [],
    }


def load_story(story_id):
    """Returns (story|None, status) with status ok | missing | corrupt."""
    return read_json(_story_file(story_id))


def save_story(story: dict) -> None:
    story["sync"]["dirty"] = True
    write_json(_story_file(story["story_id"]), story)


def list_local_stories() -> list:
    out = []
    d = store_dir() / "stories"
    if d.exists():
        for p in sorted(d.glob("story-*.json")):
            obj, st = read_json(p)
            out.append({"story_id": p.stem[6:], "status": st,
                        "project": (obj or {}).get("project"), "cycle": (obj or {}).get("cycle")})
    return out


def note_anomaly(story: dict, kind: str, detail: str = "") -> None:
    story["anomalies"].append({"at": iso(), "kind": kind, "detail": detail})
    story["anomalies"] = story["anomalies"][-100:]


# ------------------------------------------------------------------ session

def _session_file(sid: str) -> Path:
    return store_dir() / "sessions" / f"{sid}.json"


def load_session(sid: str) -> dict:
    obj, _ = read_json(_session_file(sid))
    if obj:
        return obj
    return {"session_id": sid, "started": iso(), "story_id": None, "active_stage": None,
            "trigger": None, "prompt_start": None, "prompt_chars": 0, "last_response_at": None,
            "stage_run_open": False, "forced": {}, "subagents": {}, "failures": 0,
            "escalated": False, "warnings": [], "hooked": False}


def save_session(sess: dict) -> None:
    write_json(_session_file(sess["session_id"]), sess)


def resolve_session_id(payload: dict = None, env=None):
    """(session_id, reliable). Falls back to env then a workspace pointer (spec s7.4 caveat)."""
    env = env if env is not None else os.environ
    payload = payload or {}
    for k in ("sessionId", "session_id", "sessionID"):
        if payload.get(k):
            return str(payload[k]), True
    for k in ("COPILOT_SESSION_ID", "MDA_SESSION_ID"):
        if env.get(k):
            return env[k], True
    ptr = store_dir() / "current-session.txt"
    if ptr.exists():
        return ptr.read_text(encoding="utf-8").strip(), False
    sid = f"local-{uuid.uuid4().hex[:12]}"
    ptr.write_text(sid, encoding="utf-8")
    return sid, False


def touch_session_pointer(sid: str) -> None:
    (store_dir() / "current-session.txt").write_text(sid, encoding="utf-8")


# ------------------------------------------------------------------ setup gate

def setup_missing(story) -> list:
    """Spec s3.1: anything missing blocks pipeline work."""
    if not story:
        return ["project name", "ADO user story work item ID", "migration project? (yes/no)",
                "GitHub/Copilot account confirmation"]
    s = story["setup"]
    missing = []
    if not story.get("project"):
        missing.append("project name")
    if not story.get("story_id"):
        missing.append("ADO user story work item ID")
    if s.get("is_migration") is None:
        missing.append("is this a migration project? (yes/no)")
    elif s["is_migration"]:
        labels = {"old": "old codebase path", "new": "new codebase path",
                  "hld": "HLD reference doc path", "hlsa": "HLSA reference doc path",
                  "lld": "LLD reference doc path"}
        for k, label in labels.items():
            if not s["paths"].get(k):
                missing.append(label)
    if not s.get("account", {}).get("confirmed_login"):
        missing.append("GitHub/Copilot account confirmation (user must confirm)")
    return missing


# ------------------------------------------------------------------ stage machine

def unmet_prereqs(story: dict, stage: str) -> list:
    return [p for p in PREREQ.get(stage, []) if story["stages"][p]["status"] != "approved"]


def start_stage(story: dict, stage: str, trigger: str = None) -> dict:
    if stage not in PREREQ:
        return {"ok": False, "reason": f"unknown stage '{stage}'"}
    miss = setup_missing(story)
    if miss:
        return {"ok": False, "reason": "setup_incomplete", "missing": miss,
                "message": "Setup is incomplete. Ask the developer for: " + "; ".join(miss)}
    cur = story["stages"][stage]["status"]
    if cur == "awaiting_approval":
        return {"ok": False, "reason": "awaiting_approval",
                "message": f"Stage '{stage}' is already submitted and awaiting developer approval."}
    if cur == "approved":
        return {"ok": False, "reason": "already_approved",
                "message": f"Stage '{stage}' is already approved in cycle {story['cycle']}. "
                           "Ask the developer whether to reopen (pr-review, sonar-recheck, "
                           "qa-defect or dev-reopen)."}
    unmet = unmet_prereqs(story, stage)
    if unmet:
        return {"ok": False, "reason": "prerequisite_not_approved", "unmet": unmet,
                "message": f"'{stage}' needs approved: {', '.join(unmet)}. Tell the developer "
                           "and ask whether to run the missing stage first."}
    e = story["stages"][stage]
    e.update({"status": "in_progress", "started_at": e.get("started_at") or iso(),
              "trigger": trigger or story.get("current_trigger")})
    log_stage_event(story, stage, "start")
    return {"ok": True, "stage": stage, "cycle": story["cycle"], "trigger": e["trigger"]}


def submit_stage(story: dict, stage: str, summary: str, require_artifact: bool = True) -> dict:
    e = story["stages"].get(stage)
    if not e or e["status"] != "in_progress":
        return {"ok": False, "reason": f"stage '{stage}' is not in_progress"}
    art = artifact_path(story["story_id"], stage)
    if require_artifact and not art.exists():
        return {"ok": False, "reason": "artifact_missing",
                "message": f"Write the stage artifact to {art} before submitting."}
    e.update({"status": "awaiting_approval", "submitted_at": iso(), "summary": summary,
              "artifact": str(art.relative_to(repo_root())) if art.exists() else None})
    log_stage_event(story, stage, "submit")
    return {"ok": True, "stage": stage, "status": "awaiting_approval"}


def approve_stage(story: dict, stage: str, note: str = "") -> dict:
    story["stages"][stage].update({"status": "approved", "approved_at": iso(),
                                   "approval_note": note})
    log_stage_event(story, stage, "approve")
    return {"ok": True, "stage": stage, "status": "approved"}


def request_changes(story: dict, stage: str, text: str) -> dict:
    e = story["stages"][stage]
    e["status"] = "in_progress"
    e["revisions"] = e.get("revisions", 0) + 1
    e.setdefault("change_requests", []).append({"at": iso(), "text": text[:2000]})
    log_stage_event(story, stage, "changes")
    return {"ok": True, "stage": stage, "status": "in_progress", "revisions": e["revisions"]}


AUTO_CHAIN = ["requirements", "discovery", "plan", "build", "quality", "pr"]


def next_auto_stage(story: dict):
    """Next stage auto-continue may start, or None. The chain ends at pr: the developer pushes and
    opens the PR, and QA / post-PR fixes are always explicit commands."""
    for st in AUTO_CHAIN:
        if story["stages"][st]["status"] != "approved":
            return st if not unmet_prereqs(story, st) else None
    return None


def awaiting_stage(story: dict):
    for s, e in story["stages"].items():
        if e["status"] == "awaiting_approval":
            return s
    return None


def reopen(story: dict, trigger: str, reason: str = "") -> dict:
    """Spec s6/s10: appends to the same story history; the cycle increments only if the story
    had been marked complete. Re-entry goes through build -> quality in full."""
    if trigger not in TRIGGERS:
        return {"ok": False, "reason": f"trigger must be one of {TRIGGERS}"}
    if story["stages"]["pr"]["status"] != "approved":
        return {"ok": False, "reason": "PR stage not approved yet; nothing to reopen. "
                                       "Use the normal stage commands."}
    bumped = story["complete"]
    if bumped:
        story["cycle_history"].append({
            "cycle": story["cycle"], "closed_at": story.get("completed_at"),
            "trigger": story.get("current_trigger"), "stages": copy.deepcopy(story["stages"])})
        story["cycle"] += 1
        story["complete"] = False
        story["closed"] = False
    reset = ["build", "quality"] + (["qa_execution"] if trigger == "qa-defect" else [])
    for s in reset:
        story["stages"][s] = {"status": "not_started", "trigger": trigger}
    story["current_trigger"] = trigger
    story["reopen_log"] = story.get("reopen_log", []) + [
        {"at": iso(), "trigger": trigger, "reason": reason, "cycle": story["cycle"],
         "cycle_incremented": bumped}]
    return {"ok": True, "cycle": story["cycle"], "cycle_incremented": bumped,
            "trigger": trigger}


def mark_complete(story: dict, complete: bool) -> dict:
    """Checkpoint after PR raise (spec s6): yes finalises this cycle, not permanently."""
    if story["stages"]["pr"]["status"] != "approved":
        return {"ok": False, "reason": "PR stage must be approved before the completion checkpoint"}
    story["complete"] = bool(complete)
    if complete:
        story["completed_at"] = iso()
    return {"ok": True, "complete": story["complete"], "cycle": story["cycle"]}


def qa_outcome(story: dict, outcome: str, reason: str = "") -> dict:
    if outcome == "pass":
        story["closed"] = True
        story["stages"]["qa_execution"].update({"status": "approved", "approved_at": iso()})
        return {"ok": True, "closed": True}
    if outcome == "reopen":
        if not story["complete"]:
            story["complete"] = True  # a QA reopen presupposes dev completed the cycle
            story["completed_at"] = iso()
        return reopen(story, "qa-defect", reason)
    return {"ok": False, "reason": "outcome must be pass|reopen"}
