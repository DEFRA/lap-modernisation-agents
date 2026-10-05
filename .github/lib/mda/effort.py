"""Effort tracking (spec s7). Only bounded, explicit active intervals are ever summed.

Stage active effort = sum(AI processing time across prompts) + (approval ts - last agent response ts)
Never (last event - first event). Nights/meetings produce no events, so they never count.

Entry kinds: ai | approval | manual are ACTIVE (summed); subagent is breakdown only; usage carries
real token counts (OpenTelemetry) and no time.
"""
from __future__ import annotations

import datetime as dt
import uuid

from .core import iso, load_config, local_tz, parse_ts
from .state import PHASES, phase_of

ACTIVE_KINDS = ("ai", "approval", "manual")  # 'subagent' entries are breakdown only (no double count)


def add_entry(story: dict, *, session_id, stage, kind, start, end, agent=None, est_tokens=0,
              actual_credits=None, trigger=None, cfg=None, note=None, slash_cmd=None,
              developer=None, tokens_in=None, tokens_out=None, token_source=None, model=None,
              entry_id=None) -> dict:
    """Appends (or, for a given `entry_id`, replaces) one interval.

    Capping rules: an AI turn longer than `turn_cap_minutes` is capped (it did run; flagged).
    An approval gap longer than `approval_gap_cap_minutes` is IDLE - the developer was away - and
    contributes 0 seconds (flagged `idle_excluded`) rather than a made-up 2 hours."""
    cfg = cfg or load_config()
    s, e = parse_ts(start), parse_ts(end)
    raw = max(0.0, (e - s).total_seconds())
    secs, capped, idle = raw, False, False
    if kind == "usage":
        secs = 0.0
    elif kind == "ai":
        cap = cfg["effort"]["turn_cap_minutes"]
        if cap and raw > cap * 60:
            secs, capped = cap * 60.0, True
    elif kind == "approval":
        cap = cfg["effort"]["approval_gap_cap_minutes"]
        if cap and raw > cap * 60:
            secs, capped, idle = 0.0, True, True
    stage = stage or "unassigned"
    dev = developer or (story.get("setup", {}).get("account") or {}).get("confirmed_login")
    entry = {"id": entry_id or uuid.uuid4().hex[:12], "session_id": session_id, "cycle": story["cycle"],
             "stage": stage, "phase": phase_of(stage), "kind": kind,
             "trigger": trigger or story.get("current_trigger"), "start": iso(s), "end": iso(e),
             "seconds": round(secs, 3), "raw_seconds": round(raw, 3), "capped": capped,
             "idle_excluded": idle, "developer": dev,
             # estimate = prompt characters / 4; kept only as a labelled fallback, never summed with real tokens
             "est_tokens": int(est_tokens or 0),
             "tokens_in": int(tokens_in) if tokens_in is not None else None,
             "tokens_out": int(tokens_out) if tokens_out is not None else None,
             "token_source": token_source, "model": model,
             # developer-attested GitHub Copilot premium-request credits for this turn (billing unit, not a token count)
             "actual_credits": float(actual_credits) if actual_credits is not None else None,
             "agent": agent, "note": note, "slash_cmd": slash_cmd}
    if entry_id:
        story["effort"] = [x for x in story["effort"] if x["id"] != entry_id]
    story["effort"].append(entry)
    story["sync"]["dirty"] = True
    return entry


def active(entries):
    return [x for x in entries if x["kind"] in ACTIVE_KINDS]


def seconds(entries) -> float:
    return sum(x["seconds"] for x in active(entries))


# ------------------------------------------------------------ day splitting

def effective_interval(entry: dict):
    """The span that actually counts as work. A capped AI turn counts from its start for the capped
    duration only, so a stuck overnight turn does not make the next day look "worked"."""
    s, e = parse_ts(entry["start"]), parse_ts(entry["end"])
    secs = entry["seconds"]
    if secs < (e - s).total_seconds() - 1e-6:
        e = s + dt.timedelta(seconds=secs)
    return s, e


def split_by_day(entry: dict, cfg=None):
    """[(date, seconds)] apportioned by overlap with local-midnight-split days. Only days that
    actually carry counted seconds appear (an excluded idle gap yields nothing)."""
    if entry["seconds"] <= 0:
        return []
    tz = local_tz(cfg)
    s, e = effective_interval(entry)
    s, e = s.astimezone(tz), e.astimezone(tz)
    total = (e - s).total_seconds()
    if total <= 0:
        return [(s.date(), entry["seconds"])]
    out, cur = [], s
    while cur < e:
        nxt = (cur + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seg_end = min(nxt, e)
        out.append((cur.date(), entry["seconds"] * (seg_end - cur).total_seconds() / total))
        cur = seg_end
    return out


def local_date(ts, cfg=None) -> str:
    return parse_ts(ts).astimezone(local_tz(cfg)).date().isoformat()


# ------------------------------------------------------------ roll-ups

def rollup(story: dict, cfg=None) -> dict:
    """{(cycle, stage, phase): {...}} with effort and calendar duration kept separate (s7.3).
    `dates` = distinct local calendar dates that carry counted active seconds (the measured
    building block for "days"; see docs/mda/benefits-report.md)."""
    cfg = cfg or load_config()
    rows = {}
    for x in story["effort"]:
        k = (x["cycle"], x["stage"], x["phase"])
        r = rows.setdefault(k, {"cycle": x["cycle"], "stage": x["stage"], "phase": x["phase"],
                                "trigger": x.get("trigger"), "ai_seconds": 0.0,
                                "approval_seconds": 0.0, "manual_seconds": 0.0,
                                "tokens_est": 0, "tokens_in": 0, "tokens_out": 0,
                                "credits_actual": 0.0, "first": x["start"], "last": x["end"],
                                "capped": False, "idle_excluded": 0, "subagents": {}, "dates": set()})
        if x["kind"] in ACTIVE_KINDS:
            for day, _secs in split_by_day(x, cfg):
                r["dates"].add(day.isoformat())
        if x["kind"] == "ai":
            r["ai_seconds"] += x["seconds"]
            r["tokens_est"] += x.get("est_tokens", 0)
            if x.get("actual_credits") is not None:
                r["credits_actual"] += x["actual_credits"]
        elif x["kind"] == "approval":
            r["approval_seconds"] += x["seconds"]
        elif x["kind"] == "manual":
            r["manual_seconds"] += x["seconds"]
        elif x["kind"] == "usage":
            r["tokens_in"] += x.get("tokens_in") or 0
            r["tokens_out"] += x.get("tokens_out") or 0
        elif x["kind"] == "subagent":
            r["subagents"][x.get("agent") or "?"] = r["subagents"].get(x.get("agent") or "?", 0) + x["seconds"]
        r["first"] = min(r["first"], x["start"])
        r["last"] = max(r["last"], x["end"])
        r["capped"] = r["capped"] or x.get("capped", False)
        r["idle_excluded"] += 1 if x.get("idle_excluded") else 0
        r["trigger"] = r["trigger"] or x.get("trigger")
    for r in rows.values():
        r["active_seconds"] = r["ai_seconds"] + r["approval_seconds"] + r["manual_seconds"]
        r["calendar_seconds"] = (parse_ts(r["last"]) - parse_ts(r["first"])).total_seconds()
        r["dates"] = sorted(r["dates"])
        r["active_days"] = len(r["dates"])
    return rows


def story_totals(story: dict) -> dict:
    rows = rollup(story).values()
    out = {p: 0.0 for p in PHASES}
    for r in rows:
        out[r["phase"]] = out.get(r["phase"], 0.0) + r["active_seconds"]
    ents = story["effort"]
    cal = 0.0
    if ents:
        cal = (parse_ts(max(x["end"] for x in ents)) - parse_ts(min(x["start"] for x in ents))).total_seconds()
    tin = sum(r["tokens_in"] for r in rows)
    tout = sum(r["tokens_out"] for r in rows)
    return {"active_seconds_by_phase": out, "active_seconds_total": sum(out.values()),
            "calendar_seconds": cal, "tokens_est": sum(r["tokens_est"] for r in rows),
            "tokens_in": tin, "tokens_out": tout,
            "tokens_source": "otel" if (tin or tout) else "estimate"}


def effort_rows(story: dict, cfg=None, developer=None) -> list:
    """One row per (developer, date, cycle, stage, phase): the grain that is synced to ADO, so any
    date range can be answered exactly and two developers never share a record. `developer`
    filters to one person's own entries (entries with no developer belong to the local person)."""
    cfg = cfg or load_config()
    local_dev = (story.get("setup", {}).get("account") or {}).get("confirmed_login")
    rows = {}

    def row(x, day):
        dev = x.get("developer") or local_dev
        k = (dev, day, x["cycle"], x["stage"], x["phase"])
        return rows.setdefault(k, {
            "developer": dev, "work_date": day, "cycle": x["cycle"], "stage": x["stage"],
            "phase": x["phase"], "trigger": x.get("trigger"), "ai_seconds": 0.0,
            "approval_seconds": 0.0, "manual_seconds": 0.0, "tokens_in": 0, "tokens_out": 0,
            "tokens_est": 0, "token_sources": set(), "agents": {}, "models": set(),
            "capped": 0, "idle_excluded": 0, "sessions": set()})

    for x in story["effort"]:
        dev = x.get("developer") or local_dev
        if developer and dev != developer:
            continue
        if x["kind"] in ACTIVE_KINDS:
            parts = split_by_day(x, cfg)
            if not parts and x.get("idle_excluded"):
                r = row(x, local_date(x["start"], cfg))
                r["idle_excluded"] += 1
                continue
            for day, secs in parts:
                r = row(x, day.isoformat())
                r[{"ai": "ai_seconds", "approval": "approval_seconds", "manual": "manual_seconds"}[x["kind"]]] += secs
                r["capped"] += 1 if x.get("capped") else 0
                r["sessions"].add(x["session_id"])
            if x["kind"] == "ai" and x.get("est_tokens"):
                r = row(x, local_date(x["start"], cfg))
                r["tokens_est"] += x["est_tokens"]
                r["token_sources"].add("estimate")
        elif x["kind"] == "usage":
            r = row(x, local_date(x["start"], cfg))
            r["tokens_in"] += x.get("tokens_in") or 0
            r["tokens_out"] += x.get("tokens_out") or 0
            r["token_sources"].add(x.get("token_source") or "otel")
            if x.get("model"):
                r["models"].add(x["model"])
            a = r["agents"].setdefault(x.get("agent") or "?", {"in": 0, "out": 0})
            a["in"] += x.get("tokens_in") or 0
            a["out"] += x.get("tokens_out") or 0
    out = []
    for r in rows.values():
        r["token_sources"] = sorted(r["token_sources"])
        r["models"] = sorted(r["models"])
        r["sessions"] = sorted(r["sessions"])
        out.append(r)
    return sorted(out, key=lambda r: (r["work_date"], r["developer"] or "", r["cycle"], r["stage"]))


# ------------------------------------------------------------ sprint bucketing (s7.3)

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
            b = out.setdefault(sp, {p: 0.0 for p in PHASES})
            b[x["phase"]] = b.get(x["phase"], 0.0) + secs
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
