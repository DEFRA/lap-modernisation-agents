"""Story-level usage metrics in the shape of GitHub's Copilot usage-metrics *user-level* schema
(https://docs.github.com/en/copilot/reference/copilot-usage-metrics/example-schema).

Grain matches GitHub's: one NDJSON record per (day, user_login). Ours adds the story so it is
one record per (day, user, story). GitHub field names/shapes are kept wherever the meaning is
identical, so the same downstream tooling (Power BI, Excel, dashboards) can union both feeds.

Deliberate differences:
  * `mda` extension block: everything GitHub does not track (story, cycle, stage, phase,
    trigger, sprint, active-effort seconds, complexity raw factors + weights, calibration flag).
  * `totals_by_stage` follows GitHub's `totals_by_*` array convention.
  * Fields the hooks cannot measure are null, never a fabricated 0 (LOC, output tokens, credits).
  * Token counts are ESTIMATES (prompt characters / 4); flagged in `mda.tokens_estimated`.
    Authoritative per-developer consumption is GitHub's own feed (`ai_credits_used` there).
"""
from __future__ import annotations

import json

from . import effort as E
from .core import iso, load_config, local_tz, parse_ts
from .state import phase_of

SCHEMA = "mda-user-story-day/1"


def _day(entry, tz):
    return parse_ts(entry["start"]).astimezone(tz).date().isoformat()


def build_records(story: dict, cfg=None) -> list:
    cfg = cfg or load_config()
    tz = local_tz(cfg)
    dev = story["setup"].get("account", {}).get("confirmed_login")
    cx = (story.get("complexity") or {}).get("result") or {}
    days = {}
    for x in story["effort"]:
        d = days.setdefault(_day(x, tz), [])
        d.append(x)
    sprint_of = {}
    out = []
    for day in sorted(days):
        ents = days[day]
        ai = [x for x in ents if x["kind"] == "ai"]
        sessions = {x["session_id"] for x in ents}
        slash, agents, stages = {}, {}, {}
        for x in ents:
            if x.get("slash_cmd"):
                slash[x["slash_cmd"]] = slash.get(x["slash_cmd"], 0) + 1
            if x["kind"] == "subagent" and x.get("agent"):
                agents[x["agent"]] = agents.get(x["agent"], 0) + 1
            k = (x["cycle"], x["stage"], x["phase"], x.get("trigger") or "")
            r = stages.setdefault(k, {"cycle": k[0], "stage": k[1], "phase": k[2], "trigger": k[3] or None,
                                      "interaction_count": 0, "ai_seconds": 0.0, "approval_seconds": 0.0,
                                      "manual_seconds": 0.0, "prompt_tokens_sum": 0})
            if x["kind"] == "ai":
                r["interaction_count"] += 1
                r["ai_seconds"] += x["seconds"]
                r["prompt_tokens_sum"] += x.get("est_tokens", 0)
            elif x["kind"] == "approval":
                r["approval_seconds"] += x["seconds"]
            elif x["kind"] == "manual":
                r["manual_seconds"] += x["seconds"]
        ptok = sum(x.get("est_tokens", 0) for x in ai)
        sp = E.sprint_for(__import__("datetime").date.fromisoformat(day), cfg["sprints"])
        sprint_of[day] = sp
        active = sum(x["seconds"] for x in E.active(ents))
        out.append({
            "day": day,
            "enterprise_id": cfg.get("usage", {}).get("enterprise_id"),
            "user_id": None,                      # not available from hooks; join on user_login
            "user_login": dev,
            "user_initiated_interaction_count": len(ai),
            "code_generation_activity_count": None,
            "code_acceptance_activity_count": None,
            "loc_added_sum": None, "loc_deleted_sum": None,
            "loc_suggested_to_add_sum": None, "loc_suggested_to_delete_sum": None,
            "ai_credits_used": None,              # developer-level, from GitHub's own feed
            "used_cli": True, "used_agent": True, "used_chat": False, "used_copilot_app": False,
            "used_copilot_cloud_agent": False, "used_copilot_coding_agent": False,
            "used_vscode_agent": False,
            "distinct_custom_agent_use_count": len(agents),
            "distinct_slash_cmd_use_count": len(slash),
            "distinct_skill_use_count": None, "distinct_mcp_use_count": None,
            "distinct_plugin_use_count": None,
            "totals_by_cli": {
                "prompt_count": len(ai), "request_count": len(ai), "session_count": len(sessions),
                "token_usage": {"prompt_tokens_sum": ptok, "output_tokens_sum": None,
                                "avg_tokens_per_request": round(ptok / len(ai), 1) if ai else None},
            },
            "totals_by_custom_agent": [{"custom_agent": k, "interaction_count": v} for k, v in sorted(agents.items())],
            "totals_by_slash_cmd": [{"slash_cmd": k, "interaction_count": v} for k, v in sorted(slash.items())],
            "totals_by_language_model": [], "totals_by_skill": [], "totals_by_mcp": [],
            "totals_by_stage": [{**v, "ai_seconds": round(v["ai_seconds"], 1),
                                 "approval_seconds": round(v["approval_seconds"], 1),
                                 "manual_seconds": round(v["manual_seconds"], 1)}
                                for _, v in sorted(stages.items())],
            "mda": {
                "schema": SCHEMA, "generated_at": iso(),
                "project": story["project"], "story_id": story["story_id"], "cycle_current": story["cycle"],
                "sprint": sp, "active_seconds": round(active, 1),
                "active_seconds_by_phase": {p: round(sum(x["seconds"] for x in E.active(ents) if x["phase"] == p), 1)
                                            for p in ("dev", "qa-authoring", "qa-execution")},
                "capped_intervals": sum(1 for x in ents if x.get("capped")),
                "tokens_estimated": True,
                "complexity": ({"model_version": cx.get("model_version"), "calibrated": cx.get("calibrated"),
                                "tier": cx.get("tier"), "score": cx.get("score"),
                                "counts": cx.get("counts"), "weights": cx.get("weights"),
                                "traditional_days": cx.get("traditional_days")} if cx else None),
            },
        })
    return out


def to_ndjson(records: list) -> str:
    return "\n".join(json.dumps(r, sort_keys=True, default=str) for r in records) + ("\n" if records else "")
