"""Local cache <-> ADO sync (spec s3.2). ADO is the source of truth; the local file is a cache.

Triggers: every approval-gate event, an opportunistic heartbeat on any hook event, and a
light drift check every Nth prompt. Sync failures never raise into a hook: the story is left
`dirty` and retried on the next trigger.
"""
from __future__ import annotations

import hashlib
import json

from . import effort as E
from .ado import AdoClient, AdoError
from .core import iso, load_config, parse_ts, utcnow
from .state import list_local_stories, load_story, note_anomaly, save_story


def state_key(story_id) -> str:
    return f"MDA-{story_id}-state"


def row_key(story: dict, cycle, stage, phase) -> str:
    return f"MDA-{story['story_id']}-c{cycle}-{stage}-{phase}"


def build_rows(story: dict, cfg=None) -> dict:
    """One analytics row per (cycle, stage, phase) plus the story's complexity data (s11)."""
    cfg = cfg or load_config()
    cx = (story.get("complexity") or {}).get("result") or {}
    dev = story["setup"].get("account", {}).get("confirmed_login")
    rows = {}
    for k, r in E.rollup(story).items():
        rows[row_key(story, *k)] = {
            "project": story["project"], "story_id": int(story["story_id"]) if str(story["story_id"]).isdigit() else 0,
            "sprint": E.dominant_sprint(story, k, cfg), "cycle": r["cycle"], "stage": r["stage"],
            "phase": r["phase"], "trigger": r.get("trigger") or "",
            "factors": json.dumps(cx.get("counts")) if cx else None,
            "weights": json.dumps(cx.get("weights")) if cx else None,
            "tier": cx.get("tier"),
            "traditional_days": (cx.get("traditional_days") or {}).get("point"),
            "effort_hours": E.hours(r["active_seconds"]),
            "calendar_hours": E.hours(r["calendar_seconds"]),
            "developer": dev, "tokens": r["tokens_est"], "recorded_at": iso(),
        }
    return rows


def _row_hash(fields: dict) -> str:
    body = {k: v for k, v in fields.items() if k != "recorded_at"}
    return hashlib.sha1(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _client(story, timeout=None):
    return AdoClient(project=story["project"], timeout=timeout)


def push(story: dict, reason: str, client=None, hook: bool = False) -> dict:
    cfg = load_config()
    c = client or _client(story, cfg["sync"]["hook_http_timeout_seconds"] if hook else None)
    if not c.configured:
        return {"ok": False, "reason": "ado_not_configured", "dirty": True}
    try:
        rev = story["sync"]["revision"] + 1
        snap = json.loads(json.dumps(story, default=str))
        snap["sync"]["revision"] = rev
        snap.pop("_sha", None)
        rows_done = 0
        for key, fields in build_rows(story, cfg).items():
            h = _row_hash(fields)
            if story["sync"]["row_hashes"].get(key) == h:
                continue
            c.upsert_record(key, fields, json.dumps(fields), story_ref=int(story["story_id"])
                            if str(story["story_id"]).isdigit() else None)
            story["sync"]["row_hashes"][key] = h
            rows_done += 1
        c.upsert_record(state_key(story["story_id"]),
                        {"project": story["project"], "story_id": snap["story_id"], "cycle": story["cycle"],
                         "stage": "state", "recorded_at": iso()},
                        json.dumps(snap, default=str),
                        story_ref=int(story["story_id"]) if str(story["story_id"]).isdigit() else None)
        story["sync"].update({"revision": rev, "last_sync": iso(), "dirty": False, "last_reason": reason})
        return {"ok": True, "reason": reason, "revision": rev, "rows_written": rows_done}
    except AdoError as e:
        story["sync"]["dirty"] = True
        note_anomaly(story, "sync_failed", f"{reason}: {e}")
        return {"ok": False, "reason": "ado_error", "detail": str(e), "dirty": True}


def merge_remote(local: dict, remote: dict) -> dict:
    """Adopt the remote record if newer; union effort entries by id so nothing local is lost."""
    if remote["sync"]["revision"] > local["sync"]["revision"]:
        merged = remote
        have = {x["id"] for x in merged["effort"]}
        merged["effort"] += [x for x in local["effort"] if x["id"] not in have]
        merged.setdefault("anomalies", []).extend(local.get("anomalies", [])[-10:])
        merged["setup"]["account"] = merged["setup"].get("account") or local["setup"].get("account", {})
        return merged
    have = {x["id"] for x in local["effort"]}
    local["effort"] += [x for x in remote["effort"] if x["id"] not in have]
    return local


def recover(story_id, client=None, project=None):
    """Rebuild local context from the last state synced to ADO."""
    c = client or AdoClient(project=project)
    if not c.configured:
        return None, "ado_not_configured"
    try:
        remote = c.read_payload(state_key(story_id))
    except AdoError as e:
        return None, f"ado_error: {e}"
    if not remote:
        return None, "no_remote_state"
    remote["sync"]["dirty"] = False
    return remote, "recovered"


def check(story: dict, client=None, hook: bool = True) -> dict:
    """Light drift check (every Nth prompt): confirm project/story still match ADO and pull updates."""
    cfg = load_config()
    c = client or _client(story, cfg["sync"]["hook_http_timeout_seconds"] if hook else None)
    story["sync"]["last_check"] = iso()
    if not c.configured:
        return {"ok": False, "reason": "ado_not_configured"}
    try:
        remote = c.read_payload(state_key(story["story_id"]))
    except AdoError as e:
        return {"ok": False, "reason": "ado_error", "detail": str(e)}
    if not remote:
        return {"ok": True, "drift": False, "note": "no remote state yet"}
    if remote.get("project") != story["project"] or str(remote.get("story_id")) != str(story["story_id"]):
        note_anomaly(story, "drift_mismatch", f"remote={remote.get('project')}/{remote.get('story_id')}")
        return {"ok": False, "reason": "drift_mismatch",
                "message": "Local project/story does not match ADO. Stop and ask the developer."}
    if remote["sync"]["revision"] > story["sync"]["revision"]:
        merged = merge_remote(story, remote)
        story.clear()
        story.update(merged)
        return {"ok": True, "drift": True, "pulled_revision": remote["sync"]["revision"]}
    return {"ok": True, "drift": False}


def heartbeat_due(story: dict, cfg=None) -> bool:
    cfg = cfg or load_config()
    s = story["sync"]
    if not s.get("dirty"):
        return False
    if not s.get("last_sync"):
        return True
    return (utcnow() - parse_ts(s["last_sync"])).total_seconds() >= cfg["sync"]["heartbeat_seconds"]


def flush_all(reason="heartbeat") -> list:
    out = []
    for s in list_local_stories():
        st, status = load_story(s["story_id"])
        if st and st["sync"].get("dirty"):
            r = push(st, reason)
            save_story_clean(st)
            out.append({"story_id": s["story_id"], **r})
    return out


def save_story_clean(story: dict) -> None:
    """Persist without re-marking dirty (used right after a successful push)."""
    from .core import write_json
    from .state import _story_file
    write_json(_story_file(story["story_id"]), story)
