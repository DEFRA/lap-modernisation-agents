"""Local cache <-> ADO sync (spec s3.2). ADO is the source of truth; the local file is a cache.

Records written per story (all tagged `record_tag`, all in the story's own ADO project):
  * effort rows   MDA-<story>-<developer>-<date>-c<cycle>-<stage>   one per developer/day/stage,
                  so a date range is answered exactly and two developers never share a record
  * estimate      MDA-<story>-estimate                              traditional-effort estimate +
                  complexity + application header data (written once the plan is scored)
  * state         MDA-<story>-state-<developer>                     recovery snapshot, one per
                  developer; recovery/check MERGE all of them by effort-entry id (never last-writer-wins)

Triggers: every approval-gate event, an opportunistic heartbeat on any hook event, and a light drift
check every Nth prompt. Sync failures never raise into a hook: the story is left `dirty` and retried.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import effort as E
from .ado import AdoClient, AdoError
from .core import iso, load_config, parse_ts, utcnow
from .state import list_local_stories, load_story, note_anomaly, save_story

# story-level (not per-developer) state: adopted from the remote copy when that one is newer
SHARED_KEYS = ("stages", "cycle", "cycle_history", "complete", "closed", "completed_at",
               "current_trigger", "pr", "complexity", "reopen_log", "estimate")


def _dev(story) -> str:
    login = (story.get("setup", {}).get("account") or {}).get("confirmed_login")
    return re.sub(r"[^A-Za-z0-9_.@-]", "_", login) if login else "unknown"


def state_key(story_id, developer="unknown") -> str:
    return f"MDA-{story_id}-state-{developer}"


def state_prefix(story_id) -> str:
    return f"MDA-{story_id}-state"  # also matches pre-2.0 keys (no developer suffix)


def estimate_key(story_id) -> str:
    return f"MDA-{story_id}-estimate"


def row_key(story: dict, developer, day, cycle, stage) -> str:
    dev = re.sub(r"[^A-Za-z0-9_.@-]", "_", developer) if developer else "unknown"
    return f"MDA-{story['story_id']}-{dev}-{day}-c{cycle}-{stage}"


def _story_int(story):
    return int(story["story_id"]) if str(story["story_id"]).isdigit() else 0


def _src(sources) -> str:
    return "otel" if "otel" in sources else "estimate" if "estimate" in sources else "none"


def build_rows(story: dict, cfg=None) -> dict:
    """The local developer's own per-day rows (other developers' entries merged from ADO are
    theirs to write, under their own keys)."""
    cfg = cfg or load_config()
    me = (story["setup"].get("account") or {}).get("confirmed_login")
    rows = {}
    for r in E.effort_rows(story, cfg, developer=me):
        dev = r["developer"] or me
        day = r["work_date"]
        active = r["ai_seconds"] + r["approval_seconds"] + r["manual_seconds"]
        rows[row_key(story, dev, day, r["cycle"], r["stage"])] = {
            "record_type": "effort", "project": story["project"], "story_id": _story_int(story),
            "developer": dev, "work_date": day,
            "sprint": E.sprint_for(__import__("datetime").date.fromisoformat(day), cfg["sprints"]),
            "cycle": r["cycle"], "stage": r["stage"], "phase": r["phase"], "trigger": r.get("trigger") or "",
            "ai_hours": E.hours(r["ai_seconds"]), "approval_hours": E.hours(r["approval_seconds"]),
            "manual_hours": E.hours(r["manual_seconds"]), "effort_hours": E.hours(active),
            "tokens_in": r["tokens_in"], "tokens_out": r["tokens_out"], "tokens_est": r["tokens_est"],
            "token_source": _src(r["token_sources"]),
            # payload-only detail
            "agents": r["agents"], "models": r["models"], "sessions": r["sessions"],
            "capped": r["capped"], "idle_excluded": r["idle_excluded"],
            "recorded_at": iso(),
        }
    return rows


def build_estimate(story: dict):
    """(key, fields, payload dict) for the story-level estimate record, or None if not scored yet."""
    cx = (story.get("complexity") or {}).get("result") or {}
    est = story.get("estimate")
    if not cx and not est:
        return None
    fields = {"record_type": "estimate", "project": story["project"], "story_id": _story_int(story),
              "developer": _dev(story), "tier": cx.get("tier"),
              "traditional_pd": (est or {}).get("total_pd"), "recorded_at": iso()}
    payload = {**fields, "application": story["setup"].get("application"),
               "tech_stack": story["setup"].get("tech_stack"), "complexity": cx or None,
               "estimate": est}
    return estimate_key(story["story_id"]), fields, payload


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
    ref = int(story["story_id"]) if str(story["story_id"]).isdigit() else None
    try:
        rev = story["sync"]["revision"] + 1
        snap = json.loads(json.dumps(story, default=str))
        snap["sync"]["revision"] = rev
        snap.pop("_sha", None)
        rows_done = 0
        todo = {k: (f, f) for k, f in build_rows(story, cfg).items()}  # key -> (structured fields, payload)
        est = build_estimate(story)
        if est:
            todo[est[0]] = (est[1], est[2])
        for key, (fields, payload) in todo.items():
            h = _row_hash(payload)
            if story["sync"]["row_hashes"].get(key) == h:
                continue
            c.upsert_record(key, fields, json.dumps(payload, default=str), story_ref=ref)
            story["sync"]["row_hashes"][key] = h
            rows_done += 1
        c.upsert_record(state_key(story["story_id"], _dev(story)),
                        {"record_type": "state", "project": story["project"], "story_id": _story_int(story),
                         "developer": _dev(story), "cycle": story["cycle"], "stage": "state",
                         "recorded_at": iso()},
                        json.dumps(snap, default=str), story_ref=ref)
        story["sync"].update({"revision": rev, "last_sync": iso(), "dirty": False, "last_reason": reason})
        return {"ok": True, "reason": reason, "revision": rev, "rows_written": rows_done}
    except AdoError as e:
        story["sync"]["dirty"] = True
        note_anomaly(story, "sync_failed", f"{reason}: {e}")
        return {"ok": False, "reason": "ado_error", "detail": str(e), "dirty": True}


def merge_remote(local: dict, remote: dict) -> dict:
    """Union effort entries by id (nothing from either side is lost); adopt the remote's story-level
    state (stages, cycle, complexity, estimate...) only when the remote copy is newer. The local
    developer's own account is never replaced by someone else's."""
    have = {x["id"] for x in local["effort"]}
    new = [x for x in remote["effort"] if x["id"] not in have]
    local["effort"] += new
    seen = {(a.get("at"), a.get("kind"), a.get("detail")) for a in local.get("anomalies", [])}
    local.setdefault("anomalies", []).extend(
        a for a in remote.get("anomalies", [])[-10:] if (a.get("at"), a.get("kind"), a.get("detail")) not in seen)
    ev = {(e["at"], e["stage"], e["event"]): e for e in local.get("stage_events", [])}
    ev.update({(e["at"], e["stage"], e["event"]): e for e in remote.get("stage_events", [])})
    local["stage_events"] = sorted(ev.values(), key=lambda e: e["at"])
    newer = (remote["sync"].get("revision", 0) > local["sync"].get("revision", 0)
             or (remote["sync"].get("last_sync") or "") > (local["sync"].get("last_sync") or "~"))
    if newer or new:
        local["sync"]["dirty"] = True
    if newer:
        for k in SHARED_KEYS:
            if k in remote:
                local[k] = remote[k]
        for k in ("application", "tech_stack"):
            if remote["setup"].get(k) and not local["setup"].get(k):
                local["setup"][k] = remote["setup"][k]
    return local


def recover(story_id, client=None, project=None):
    """Rebuild local context from every developer's last-synced state snapshot, merged."""
    c = client or AdoClient(project=project)
    if not c.configured:
        return None, "ado_not_configured"
    try:
        remotes = c.read_payloads(state_prefix(story_id))
    except AdoError as e:
        return None, f"ado_error: {e}"
    if not remotes:
        return None, "no_remote_state"
    remotes.sort(key=lambda r: r["sync"].get("last_sync") or "")
    base = remotes[-1]
    for other in remotes[:-1]:
        merge_remote(base, other)
    base["sync"]["dirty"] = False
    return base, "recovered"


def check(story: dict, client=None, hook: bool = True) -> dict:
    """Light drift check (every Nth prompt): confirm project/story still match ADO and merge in other
    developers' work."""
    cfg = load_config()
    c = client or _client(story, cfg["sync"]["hook_http_timeout_seconds"] if hook else None)
    story["sync"]["last_check"] = iso()
    if not c.configured:
        return {"ok": False, "reason": "ado_not_configured"}
    try:
        remotes = c.read_payloads(state_prefix(story["story_id"]))
    except AdoError as e:
        return {"ok": False, "reason": "ado_error", "detail": str(e)}
    if not remotes:
        return {"ok": True, "drift": False, "note": "no remote state yet"}
    for remote in remotes:
        if remote.get("project") != story["project"] or str(remote.get("story_id")) != str(story["story_id"]):
            note_anomaly(story, "drift_mismatch", f"remote={remote.get('project')}/{remote.get('story_id')}")
            return {"ok": False, "reason": "drift_mismatch",
                    "message": "Local project/story does not match ADO. Stop and ask the developer."}
    before = len(story["effort"])
    for remote in remotes:
        merge_remote(story, remote)
    pulled = len(story["effort"]) - before
    return {"ok": True, "drift": bool(pulled), "pulled_entries": pulled}


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
