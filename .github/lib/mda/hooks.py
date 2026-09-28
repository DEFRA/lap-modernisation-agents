"""Copilot CLI hook handlers (spec s5, s7.4). Every handler is failure-tolerant: a bug or an
ADO outage must never break the developer's session. Verify payload field names against your
Copilot CLI version (spec s15: sessionId reliability) - lookups here are deliberately lenient.
"""
from __future__ import annotations

import json
import os
import re

from . import effort as E
from . import gate, sync
from .core import iso, load_config, parse_ts
from .state import (SUBAGENT_STAGE, next_auto_stage, approve_stage, artifact_path, awaiting_stage, load_session,
                    load_story, note_anomaly, request_changes, resolve_session_id, save_session,
                    save_story, setup_missing, touch_session_pointer)
from .sync import save_story_clean


def _g(payload: dict, *keys, default=None):
    for k in keys:
        if payload.get(k) not in (None, ""):
            return payload[k]
    return default


def _ctx(payload):
    sid, reliable = resolve_session_id(payload)
    sess = load_session(sid)
    sess["hooked"] = True  # any hook event firing for this session proves the hook layer is live
    if not reliable and "session_id_unreliable" not in sess["warnings"]:
        sess["warnings"].append("session_id_unreliable")
    story = None
    if sess.get("story_id"):
        story, status = load_story(sess["story_id"])
        if status == "corrupt":
            story = _try_recover(sess)
    return sid, sess, story


def _try_recover(sess):
    remote, why = sync.recover(sess["story_id"])
    if remote:
        save_story_clean(remote)
        return remote
    return None


def _heartbeat(story):
    if story and sync.heartbeat_due(story):
        sync.push(story, "heartbeat", hook=True)


def handle_session_start(payload: dict) -> dict:
    sid, sess, story = _ctx(payload)
    touch_session_pointer(sid)
    msg = []
    if sess.get("story_id") and story is None:
        msg.append(f"Local cache for story {sess['story_id']} is missing/corrupt and ADO recovery failed.")
    if story:
        _heartbeat(story)
    save_session(sess)
    try:
        from . import usage
        usage.maybe_daily_sync(story)
    except Exception:
        pass
    return {"systemMessage": " ".join(msg)} if msg else {}


def handle_user_prompt(payload: dict) -> dict:
    sid, sess, story = _ctx(payload)
    ts = parse_ts(_g(payload, "timestamp", "ts"))
    prompt = _g(payload, "prompt", "userPrompt", "text", default="") or ""
    out = {}
    if story is None:
        sess["prompt_start"] = iso(ts)
        save_session(sess)
        return out
    cfg = load_config()
    story["sync"]["prompt_count"] += 1
    sess["failures"], sess["escalated"] = 0, False
    verdict, text = gate.classify_prompt(prompt)
    waiting = awaiting_stage(story)
    if verdict and waiting:
        # (approval ts - last agent response ts) is active effort (spec s7.2)
        E.add_entry(story, session_id=sid, stage=waiting, kind="approval",
                    start=sess.get("last_response_at") or ts, end=ts, cfg=cfg,
                    note=verdict)
        if verdict == "approve":
            approve_stage(story, waiting, text)
            sess["stage_run_open"], sess["active_stage"] = False, None
            r = sync.push(story, f"gate:{waiting}:approved", hook=True)
            nxt = next_auto_stage(story) if story["setup"].get("auto_continue") else None
            if nxt:
                follow = (f"Auto-continue is ON: start stage '{nxt}' now (same stage loop, it still "
                          "ends at its own approval gate).")
            else:
                follow = ("Auto-continue is OFF or the chain has ended: offer the next command and wait; "
                          "do not start another stage unless the developer asks.")
            out["additionalContext"] = (f"Developer APPROVED stage '{waiting}'. {follow} "
                                        f"Sync: {r.get('reason')}")
        else:
            request_changes(story, waiting, text)
            sess["stage_run_open"], sess["active_stage"] = True, waiting
            sess["forced"] = {}
            sync.push(story, f"gate:{waiting}:changes", hook=True)
            out["additionalContext"] = (f"Developer requested CHANGES on stage '{waiting}': {text}. "
                                        "Revise and resubmit to the same gate.")
    else:
        E_pending = sess.get("prompt_start")
        if E_pending and sess.get("last_response_at") is None:
            note_anomaly(story, "prompt_without_stop", "previous turn never reported agentStop")
    sess["prompt_start"] = iso(ts)
    sess["prompt_chars"] = len(prompt)
    m = re.match(r"^\s*/([\w-]+)", prompt)
    sess["slash_cmd"] = ("/" + m.group(1)) if m else None
    n = cfg["sync"]["check_every_n_prompts"]
    if n and story["sync"]["prompt_count"] % n == 0:
        res = sync.check(story, hook=True)
        if res.get("reason") == "drift_mismatch":
            out["additionalContext"] = res["message"]
    _heartbeat(story)
    save_story_clean(story) if not story["sync"]["dirty"] else save_story(story)
    save_session(sess)
    return out


def handle_agent_stop(payload: dict) -> dict:
    sid, sess, story = _ctx(payload)
    ts = parse_ts(_g(payload, "timestamp", "ts"))
    out = {}
    if story is None:
        save_session(sess)
        return out
    cfg = load_config()
    stage = sess.get("active_stage")
    if sess.get("prompt_start"):
        E.add_entry(story, session_id=sid, stage=stage, kind="ai", start=sess["prompt_start"], end=ts,
                    est_tokens=sess.get("prompt_chars", 0) // 4, cfg=cfg, agent="orchestrator",
                    slash_cmd=sess.get("slash_cmd"))
        sess["prompt_start"] = None
    sess["last_response_at"] = iso(ts)
    # Block + force continuation only if a stage run is open and was never submitted to the gate.
    if stage and sess.get("stage_run_open") and story["stages"].get(stage, {}).get("status") == "in_progress":
        used = sess["forced"].get(stage, 0)
        if used < cfg["gates"]["max_forced_continuations"]:
            sess["forced"][stage] = used + 1
            out = {"decision": "block", "reason": (
                f"Stage '{stage}' is in progress but has not reached its approval gate. Finish the stage, "
                f"write the artifact to {artifact_path(story['story_id'], stage)}, then run "
                f"`python .github/scripts/mda.py gate submit --stage {stage} --summary \"...\"`. "
                f"If you genuinely need input from the developer, run `mda.py stage wait-input` and ask.")}
    _heartbeat(story)
    save_story_clean(story) if not story["sync"]["dirty"] else save_story(story)
    save_session(sess)
    return out


def handle_subagent_start(payload: dict) -> dict:
    sid, sess, story = _ctx(payload)
    name = _g(payload, "agentName", "subagentName", "agent_name", "name", "agent", default="subagent")
    sess["subagents"][str(name)] = iso(parse_ts(_g(payload, "timestamp", "ts")))
    save_session(sess)
    return {}


def handle_subagent_stop(payload: dict) -> dict:
    sid, sess, story = _ctx(payload)
    ts = parse_ts(_g(payload, "timestamp", "ts"))
    name = str(_g(payload, "agentName", "subagentName", "agent_name", "name", "agent", default="subagent"))
    start = sess["subagents"].pop(name, None)
    out = {}
    if story is not None and start:
        E.add_entry(story, session_id=sid, stage=SUBAGENT_STAGE.get(name, sess.get("active_stage")),
                    kind="subagent", start=start, end=ts, agent=name)
        stage = SUBAGENT_STAGE.get(name)
        cfg = load_config()
        if (stage and sess.get("active_stage") == stage and sess.get("stage_run_open")
                and not artifact_path(story["story_id"], stage).exists()):
            key = f"sub:{name}"
            if sess["forced"].get(key, 0) < cfg["gates"]["max_forced_continuations"]:
                sess["forced"][key] = sess["forced"].get(key, 0) + 1
                out = {"decision": "block", "reason": (
                    f"{name} has not written its stage artifact "
                    f"({artifact_path(story['story_id'], stage)}). Produce it before stopping.")}
        save_story(story)
    save_session(sess)
    return out


def handle_tool_gate(payload: dict) -> dict:
    """permissionRequest / preToolUse. Emits both common deny shapes; unknown keys are ignored."""
    sid, sess, story = _ctx(payload)
    name = _g(payload, "toolName", "tool_name", "tool", default="")
    args = _g(payload, "toolArgs", "tool_input", "toolInput", "arguments", default={})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            pass
    d = gate.tool_decision(name, args,
                           setup_missing=setup_missing(story) if story else [],
                           awaiting=awaiting_stage(story) if story else None,
                           escalated=bool(sess.get("escalated")), bound=story is not None)
    if d["allow"]:
        return {}
    return {"permissionDecision": "deny", "permissionDecisionReason": d["reason"],
            "behavior": "deny", "message": d["reason"], "decision": "deny", "reason": d["reason"]}


def handle_tool_failure(payload: dict) -> dict:
    sid, sess, story = _ctx(payload)
    if story is None:
        return {}
    cfg = load_config()
    sess["failures"] = sess.get("failures", 0) + 1
    out = {}
    if sess["failures"] >= cfg["gates"]["self_heal_max_retries"] and not sess.get("escalated"):
        sess["escalated"] = True
        note_anomaly(story, "self_heal_escalated", f"{sess['failures']} consecutive tool failures")
        save_story(story)
        out = {"additionalContext": (
            f"Self-heal cap ({cfg['gates']['self_heal_max_retries']}) reached. Stop retrying, summarise "
            "the failures and ask the developer how to proceed.")}
    save_session(sess)
    return out


def handle_session_end(payload: dict) -> dict:
    sid, sess, story = _ctx(payload)
    if story is not None:
        if sess.get("prompt_start"):
            E.add_entry(story, session_id=sid, stage=sess.get("active_stage"), kind="ai",
                        start=sess["prompt_start"], end=_g(payload, "timestamp", "ts") or iso(),
                        est_tokens=sess.get("prompt_chars", 0) // 4, note="session_end_open_turn")
            sess["prompt_start"] = None
        sync.push(story, "session_end", hook=True)
        save_story_clean(story) if not story["sync"]["dirty"] else save_story(story)
    save_session(sess)
    return {}


HANDLERS = {
    "sessionStart": handle_session_start, "sessionEnd": handle_session_end,
    "userPromptSubmitted": handle_user_prompt, "agentStop": handle_agent_stop,
    "subagentStart": handle_subagent_start, "subagentStop": handle_subagent_stop,
    "permissionRequest": handle_tool_gate, "preToolUse": handle_tool_gate,
    "postToolUseFailure": handle_tool_failure, "errorOccurred": handle_tool_failure,
}


def dispatch(event: str, payload: dict) -> dict:
    fn = HANDLERS.get(event)
    if not fn:
        return {}
    try:
        return fn(payload) or {}
    except Exception as e:  # never break the developer's session
        if os.environ.get("MDA_DEBUG"):
            raise
        import sys
        print(f"[mda] hook {event} error: {e}", file=sys.stderr)
        return {}
