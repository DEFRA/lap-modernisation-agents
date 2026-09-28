"""Self-driven turn timing and gate recording for runtimes with no hook layer (e.g. a custom
agent selected from the VS Code Copilot Chat dropdown - see docs/mda/runtimes.md).

Mirrors what hooks.py does automatically under Copilot CLI, but is only ever invoked when the
orchestrator's own instructions call it, and only takes effect on an UNHOOKED session (`session
hooked` -> True once any real hook has fired) - so a session that *is* hook-enforced ignores
these calls rather than double-counting effort or double-recording an approval.

The approval commands do not trust the caller's interpretation of "the developer approved": the
literal text the developer typed must be passed in `--verbatim`, and it is re-matched here
against the same pattern hooks.py uses. This is weaker than a hook (which reads the prompt
independently of the LLM); it removes "close enough" acceptance, but cannot prove the LLM did
not fabricate the verbatim text. See docs/mda/runtimes.md for the honest limits.
"""
from __future__ import annotations

from . import effort as E
from . import gate
from .core import iso, load_config, utcnow
from .state import approve_stage, awaiting_stage, request_changes


def turn_start(sess: dict, chars: int = None) -> dict:
    if sess.get("hooked"):
        return {"ok": True, "skipped": "hooked_session"}
    sess["prompt_start"] = iso(utcnow())
    # mirrors hooks.py's handle_user_prompt: len(prompt) chars, est_tokens = chars // 4 at turn_end
    sess["prompt_chars"] = int(chars or 0)
    return {"ok": True, "started_at": sess["prompt_start"]}


def turn_end(sess: dict, story: dict, session_id: str, cfg=None, actual_credits: float = None) -> dict:
    if sess.get("hooked"):
        return {"ok": True, "skipped": "hooked_session"}
    if not sess.get("prompt_start"):
        return {"ok": False, "reason": "no_open_turn", "message": "Call `turn start` before `turn end`."}
    entry = E.add_entry(story, session_id=session_id, stage=sess.get("active_stage"), kind="ai",
                        start=sess["prompt_start"], end=utcnow(), cfg=cfg or load_config(),
                        est_tokens=sess.get("prompt_chars", 0) // 4, actual_credits=actual_credits,
                        agent="orchestrator", slash_cmd=sess.get("slash_cmd"))
    sess["last_response_at"] = entry["end"]
    sess["prompt_start"] = None
    sess["prompt_chars"] = 0
    return {"ok": True, "seconds": entry["seconds"], "capped": entry["capped"],
            "actual_credits": entry["actual_credits"]}


def _gate_action(sess, story, session_id, verbatim, expect, apply_fn, cfg=None):
    if sess.get("hooked"):
        return {"ok": False, "reason": "hooked_session",
                "message": "This session is hook-enforced; do not call gate approve/request-changes "
                          "yourself - the hook already records the developer's reply."}
    waiting = awaiting_stage(story)
    if not waiting:
        return {"ok": False, "reason": "no_stage_awaiting_approval"}
    verdict, text = gate.classify_prompt(verbatim)
    if verdict != expect:
        return {"ok": False, "reason": "verbatim_does_not_match",
                "message": f"The text passed does not read as '{expect}'. Pass the developer's reply "
                          "exactly as they typed it; do not paraphrase or infer approval."}
    entry = E.add_entry(story, session_id=session_id, stage=waiting, kind="approval",
                        start=sess.get("last_response_at") or story["stages"][waiting].get("submitted_at") or utcnow(),
                        end=utcnow(), cfg=cfg or load_config(), note=verdict)
    result = apply_fn(story, waiting, text)
    sess["stage_run_open"] = expect != "approve"
    if expect == "approve":
        sess["active_stage"] = None
    return {"ok": True, "stage": waiting, **result, "approval_seconds": entry["seconds"]}


def gate_approve(sess, story, session_id, verbatim, cfg=None):
    return _gate_action(sess, story, session_id, verbatim, "approve",
                        lambda st, w, t: approve_stage(st, w, t), cfg)


def gate_request_changes(sess, story, session_id, verbatim, cfg=None):
    return _gate_action(sess, story, session_id, verbatim, "changes",
                        lambda st, w, t: request_changes(st, w, t), cfg)
