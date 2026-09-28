"""Effort tracking (spec s7). Only bounded, explicit active intervals are ever summed.

Stage active effort = sum(AI processing time across prompts) + (approval ts - last agent response ts)
Never (last event - first event). Nights/meetings produce no events, so they never count.
"""
from __future__ import annotations

import datetime as dt
import uuid

from .core import iso, load_config, local_tz, parse_ts
from .state import phase_of

ACTIVE_KINDS = ("ai", "approval", "manual")  # 'subagent' entries are breakdown only (no double count)


def add_entry(story: dict, *, session_id, stage, kind, start, end, agent=None, est_tokens=0,
              actual_credits=None, trigger=None, cfg=None, note=None, slash_cmd=None) -> dict:
    cfg = cfg or load_config()
    cap_min = {"ai": cfg["effort"]["turn_cap_minutes"],
               "approval": cfg["effort"]["approval_gap_cap_minutes"]}.get(kind)
    s, e = parse_ts(start), parse_ts(end)
    raw = max(0.0, (e - s).total_seconds())
    secs, capped = raw, False
    if cap_min and raw > cap_min * 60:
        secs, capped = cap_min * 60.0, True  # long gaps are almost certainly the developer being away
    entry = {"id": uuid.uuid4().hex[:12], "session_id": session_id, "cycle": story["cycle"],
             "stage": stage or "setup", "phase": phase_of(stage or "setup"), "kind": kind,
             "trigger": trigger or story.get("current_trigger"), "start": iso(s), "end": iso(e),
             "seconds": round(secs, 3), "raw_seconds": round(raw, 3), "capped": capped,
             "est_tokens": int(est_tokens or 0),
             # developer-attested GitHub Copilot premium-request credits for this turn (billing unit, not a token count)
             "actual_credits": float(actual_credits) if actual_credits is not None else None,
             "agent": agent, "note": note, "slash_cmd": slash_cmd}
    story["effort"].append(entry)
    story["sync"]["dirty"] = True
    return entry


def active(entries):
    return [x for x in entries if x["kind"] in ACTIVE_KINDS]


def seconds(entries) -> float:
    return sum(x["seconds"] for x in active(entries))


def rollup(story: dict) -> dict:
    """{(cycle, stage, phase): {...}} with effort and calendar duration kept separate (s7.3)."""
    rows = {}
    for x in story["effort"]:
        k = (x["cycle"], x["stage"], x["phase"])
        r = rows.setdefault(k, {"cycle": x["cycle"], "stage": x["stage"], "phase": x["phase"],
                                "trigger": x.get("trigger"), "ai_seconds": 0.0,
                                "approval_seconds": 0.0, "manual_seconds": 0.0,
                                "tokens_est": 0, "credits_actual": 0.0, "first": x["start"], "last": x["end"],
                                "capped": False, "subagents": {}})
        if x["kind"] == "ai":
            r["ai_seconds"] += x["seconds"]
            r["tokens_est"] += x.get("est_tokens", 0)
            if x.get("actual_credits") is not None:
                r["credits_actual"] += x["actual_credits"]
        elif x["kind"] == "approval":
            r["approval_seconds"] += x["seconds"]
        elif x["kind"] == "manual":
            r["manual_seconds"] += x["seconds"]
        elif x["kind"] == "subagent":
            r["subagents"][x.get("agent") or "?"] = r["subagents"].get(x.get("agent") or "?", 0) + x["seconds"]
        r["first"] = min(r["first"], x["start"])
        r["last"] = max(r["last"], x["end"])
        r["capped"] = r["capped"] or x.get("capped", False)
        r["trigger"] = r["trigger"] or x.get("trigger")
    for r in rows.values():
        r["active_seconds"] = r["ai_seconds"] + r["approval_seconds"] + r["manual_seconds"]
        r["calendar_seconds"] = (parse_ts(r["last"]) - parse_ts(r["first"])).total_seconds()
    return rows


def story_totals(story: dict) -> dict:
    rows = rollup(story).values()
    out = {"dev": 0.0, "qa-authoring": 0.0, "qa-execution": 0.0}
    for r in rows:
        out[r["phase"]] += r["active_seconds"]
    ents = story["effort"]
    cal = 0.0
    if ents:
        cal = (parse_ts(max(x["end"] for x in ents)) - parse_ts(min(x["start"] for x in ents))).total_seconds()
    return {"active_seconds_by_phase": out, "active_seconds_total": sum(out.values()),
            "calendar_seconds": cal, "tokens_est": sum(r["tokens_est"] for r in rows)}


# ------------------------------------------------------------ sprint bucketing (s7.3)

def split_by_day(entry: dict, cfg=None):
    """Splits an interval at local midnights; seconds are apportioned by overlap."""
    tz = local_tz(cfg)
    s, e = parse_ts(entry["start"]).astimezone(tz), parse_ts(entry["end"]).astimezone(tz)
    total = max((e - s).total_seconds(), 1e-9)
    out, cur = [], s
    while cur < e:
        nxt = (cur + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seg_end = min(nxt, e)
        out.append((cur.date(), entry["seconds"] * (seg_end - cur).total_seconds() / total))
        cur = seg_end
    return out or [(s.date(), entry["seconds"])]


def sprint_for(day: dt.date, sprints) -> str:
    for sp in sprints:
        if dt.date.fromisoformat(sp["start"]) <= day <= dt.date.fromisoformat(sp["end"]):
            return sp["name"]
    return "(no sprint)"


def by_sprint(story: dict, cfg=None) -> dict:
    cfg = cfg or load_config()
    out = {}
    for x in active(story["effort"]):
        for day, secs in split_by_day(x, cfg):
            sp = sprint_for(day, cfg["sprints"])
            b = out.setdefault(sp, {"dev": 0.0, "qa-authoring": 0.0, "qa-execution": 0.0})
            b[x["phase"]] += secs
    return out


def dominant_sprint(story: dict, stage_key, cfg=None) -> str:
    cfg = cfg or load_config()
    tally = {}
    for x in active(story["effort"]):
        if (x["cycle"], x["stage"], x["phase"]) != stage_key:
            continue
        for day, secs in split_by_day(x, cfg):
            sp = sprint_for(day, cfg["sprints"])
            tally[sp] = tally.get(sp, 0) + secs
    return max(tally, key=tally.get) if tally else "(no sprint)"


def hours(sec: float) -> float:
    return round(sec / 3600.0, 3)
