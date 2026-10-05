"""AI Productivity (AI Efficiency) report: the "Effort saving / Time saving / Automated completion"
summary plus a per-phase Delivery Comparison, for any date range. See
.github/docs/mda/benefits-report.md for the methodology and honest limits.

Inputs are per-developer, per-day effort rows plus one story-level estimate each (the records that
sync.py writes to ADO), so any [from, to] range is answered exactly. Two front-ends, same core:
  build(project, ...)          LOCAL PREVIEW from stories cached on this machine (one developer's
                                view; not a project total).
  build_from_records(...)      the authoritative path: every developer's synced records read back from
                                ADO by .github/scripts/pipeline/export_ai_efficiency.py.

Rules that keep the comparison honest:
  * like-for-like: a story contributes to a phase row only if it has a traditional figure for that
    phase; its AI effort for phases without one is listed under `excluded`, never silently mixed in.
  * traditional effort (LLM-estimated per phase, developer-confirmed) for a date range is the story's estimate pro-rated by the share of that
    story-phase's measured AI effort that falls inside the range (full range = full estimate).
  * PD = active hours / hours-per-day. AI days = distinct calendar dates actually worked. Traditional
    days are taken equal to traditional PD (one person-day per day) - stated in the report.
  * cost is intentionally not produced.
"""
from __future__ import annotations

import json

from . import effort as E
from .core import iso, load_config, repo_root
from .state import list_local_stories, load_story

MODEL_PATH = ".github/config/mda/benefits-model.json"
TIER_ORDER = ["Low", "Medium", "High", "Very High"]
DEFINITIONS = [
    "PD (person-days) = active hours / hours-per-day (config effort.hours_per_day).",
    "AI days = distinct calendar dates on which work in that phase was actually measured.",
    "Traditional PD = the story's LLM-estimated person-days per phase (each with a reason, confirmed by the "
    "developer), pro-rated to the date range by the share of measured effort inside it. Traditional days = traditional PD.",
    "Effort saving = 1 - AI PD / Traditional PD, Time saving = 1 - AI days / Traditional days; both over the "
    "phases that have both figures only.",
    "Automated completion = share of measured active time that was the AI processing, versus developer review "
    "(approval) time and manual work. Our definition; adjust if the programme means something else.",
    "Cost columns are intentionally not produced.",
]


def load_model(path=None) -> dict:
    return json.loads((repo_root() / (path or MODEL_PATH)).read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------- input normalisation

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _decode(rec: dict, fields: dict) -> dict:
    """One ADO work-item `fields` dict -> the record dict (JSON payload first, structured fields as fallback)."""
    raw = rec.get(fields["payload"])
    if not raw:
        raw = (rec.get("System.Description") or "").replace("<pre>", "").replace("</pre>", "") \
            .replace("&lt;", "<").replace("&amp;", "&")
    try:
        row = json.loads(raw) if raw else {}
    except ValueError:
        row = {}
    if not row:
        inv = {v: k for k, v in fields.items()}
        row = {inv[k]: v for k, v in rec.items() if k in inv}
    row["_title"] = rec.get("System.Title", "")
    return row


def from_records(records: list, fields: dict, project: str):
    """(effort_rows, estimates{story_id: record}) from raw ADO work-item fields, for one project."""
    rows, estimates = [], {}
    for rec in records:
        row = _decode(rec, fields)
        if (row.get("project") or "").strip().lower() != project.strip().lower():
            continue
        kind = row.get("record_type")
        if kind == "estimate" or row["_title"].endswith("-estimate"):
            estimates[str(row.get("story_id"))] = row
        elif (kind == "effort" or kind is None) and row.get("work_date") and row.get("stage"):
            row["story_id"] = str(row.get("story_id"))
            rows.append(row)
    return rows, estimates


def from_stories(stories: list, cfg=None):
    """Same shapes, from locally cached stories (all developers' entries that this machine holds)."""
    cfg = cfg or load_config()
    rows, estimates = [], {}
    for st in stories:
        for r in E.effort_rows(st, cfg):
            rows.append({
                "story_id": str(st["story_id"]), "developer": r["developer"], "work_date": r["work_date"],
                "cycle": r["cycle"], "stage": r["stage"], "phase": r["phase"],
                "ai_hours": E.hours(r["ai_seconds"]), "approval_hours": E.hours(r["approval_seconds"]),
                "manual_hours": E.hours(r["manual_seconds"]), "tokens_in": r["tokens_in"],
                "tokens_out": r["tokens_out"], "tokens_est": r["tokens_est"], "agents": r["agents"],
                "token_source": "otel" if "otel" in r["token_sources"] else "estimate" if r["token_sources"] else "none",
                "capped": r["capped"], "idle_excluded": r["idle_excluded"]})
        cx = (st.get("complexity") or {}).get("result")
        if st.get("estimate") or cx:
            estimates[str(st["story_id"])] = {
                "story_id": str(st["story_id"]), "tier": (cx or {}).get("tier"),
                "estimate": st.get("estimate"), "application": st["setup"].get("application"),
                "tech_stack": st["setup"].get("tech_stack"), "complexity": cx}
    return rows, estimates


def project_stories(project: str) -> list:
    out = []
    for row in list_local_stories():
        if row["status"] != "ok" or (row.get("project") or "").strip().lower() != project.strip().lower():
            continue
        story, status = load_story(row["story_id"])
        if status == "ok":
            out.append(story)
    return out


# ---------------------------------------------------------------- the report

def _active_h(r) -> float:
    return _num(r.get("ai_hours")) + _num(r.get("approval_hours")) + _num(r.get("manual_hours"))


def _in_range(day, date_from, date_to) -> bool:
    return (not date_from or day >= date_from) and (not date_to or day <= date_to)


def build_report(project: str, rows: list, estimates: dict, date_from: str = None, date_to: str = None,
                 model: dict = None, cfg=None, application: str = None, tech_stack: str = None) -> dict:
    cfg = cfg or load_config()
    model = model or load_model()
    if date_from and date_to and date_from > date_to:
        raise ValueError(f"fromDate {date_from} is after toDate {date_to}")
    hpd = cfg["effort"]["hours_per_day"]
    s2p = model["stage_to_phase"]
    phases = model["phases"]

    # totals per (story, phase) over ALL dates -> the denominator for pro-rating
    total_h = {}
    for r in rows:
        ph = s2p.get(r.get("stage"))
        if ph:
            k = (r["story_id"], ph)
            total_h[k] = total_h.get(k, 0.0) + _active_h(r)

    scoped = [r for r in rows if _in_range(r["work_date"], date_from, date_to)]
    unmapped_h = sum(_active_h(r) for r in scoped if s2p.get(r.get("stage")) is None)
    mapped = [r for r in scoped if s2p.get(r.get("stage"))]

    def trad_pd(story_id, phase):
        est = (estimates.get(story_id) or {}).get("estimate") or {}
        return (est.get("phases") or {}).get(phase)

    buckets = {p: {"active_h": 0.0, "ai_h": 0.0, "dates": set(), "stories": set(), "trad_pd": 0.0}
               for p in phases}
    excluded, in_h = {}, {}
    for r in mapped:
        ph, sid = s2p[r["stage"]], r["story_id"]
        if trad_pd(sid, ph) is None:
            excluded[(sid, ph)] = excluded.get((sid, ph), 0.0) + _active_h(r)
            continue
        b = buckets[ph]
        b["active_h"] += _active_h(r)
        b["ai_h"] += _num(r.get("ai_hours"))
        if _active_h(r) > 0:
            b["dates"].add(r["work_date"])
        b["stories"].add(sid)
        in_h[(sid, ph)] = in_h.get((sid, ph), 0.0) + _active_h(r)
    for (sid, ph), hours_in_range in in_h.items():
        denom = total_h.get((sid, ph), 0.0)
        buckets[ph]["trad_pd"] += trad_pd(sid, ph) * (hours_in_range / denom if denom else 0.0)

    out_rows = []
    for ph in phases:
        b = buckets[ph]
        label = model["phase_labels"].get(ph, ph)
        if not b["stories"]:
            out_rows.append({"phase": ph, "label": label, "traditional_pd": None, "ai_pd": None,
                             "traditional_days": None, "ai_days": None, "automation_pct": None,
                             "stories": [], "evidence": "NEEDS INPUT: no measured effort with a traditional "
                                                        "estimate in this range"})
            continue
        ai_pd = round(b["active_h"] / hpd, 2)
        trad = round(b["trad_pd"], 2)
        out_rows.append({"phase": ph, "label": label, "traditional_pd": trad, "ai_pd": ai_pd,
                         "traditional_days": trad, "ai_days": len(b["dates"]),
                         "automation_pct": round(1 - ai_pd / trad, 4) if trad else None,
                         "stories": sorted(b["stories"]),
                         "evidence": f"{len(b['stories'])} stor{'y' if len(b['stories']) == 1 else 'ies'}: "
                                     + ", ".join(sorted(b["stories"]))})

    both = [r for r in out_rows if r["traditional_pd"] and r["ai_pd"] is not None]
    t_pd, a_pd = sum(r["traditional_pd"] for r in both), sum(r["ai_pd"] for r in both)
    t_d, a_d = sum(r["traditional_days"] for r in both), sum(r["ai_days"] for r in both)
    ai_all = sum(_num(r.get("ai_hours")) for r in mapped)
    act_all = sum(_active_h(r) for r in mapped)
    benefits = {"effort_saving_pct": round(1 - a_pd / t_pd, 4) if t_pd else None,
                "time_saving_pct": round(1 - a_d / t_d, 4) if t_d else None,
                "cost_saving_pct": None,
                "automated_completion_pct": round(ai_all / act_all, 4) if act_all else None,
                "totals": {"traditional_pd": round(t_pd, 2) if both else None,
                           "ai_pd": round(a_pd, 2) if both else None,
                           "traditional_days": round(t_d, 2) if both else None,
                           "ai_days": a_d if both else None}}

    # tokens: by stage and by agent (real OpenTelemetry vs estimate kept apart)
    by_stage, by_agent, src = {}, {}, {}
    for r in scoped:
        st = by_stage.setdefault(r["stage"], {"stage": r["stage"], "tokens_in": 0, "tokens_out": 0, "tokens_est": 0})
        st["tokens_in"] += int(_num(r.get("tokens_in")))
        st["tokens_out"] += int(_num(r.get("tokens_out")))
        st["tokens_est"] += int(_num(r.get("tokens_est")))
        for agent, v in (r.get("agents") or {}).items():
            a = by_agent.setdefault(agent, {"agent": agent, "tokens_in": 0, "tokens_out": 0})
            a["tokens_in"] += int(_num(v.get("in")))
            a["tokens_out"] += int(_num(v.get("out")))
        src[r.get("token_source") or "none"] = src.get(r.get("token_source") or "none", 0) + 1
    tokens = {"by_stage": sorted(by_stage.values(), key=lambda x: x["stage"]),
              "by_agent": sorted(by_agent.values(), key=lambda x: x["agent"]),
              "total_in": sum(x["tokens_in"] for x in by_stage.values()),
              "total_out": sum(x["tokens_out"] for x in by_stage.values()),
              "total_est": sum(x["tokens_est"] for x in by_stage.values()), "source_mix": src}

    story_ids = sorted({r["story_id"] for r in scoped})
    ests = [estimates[s]["estimate"] for s in story_ids if (estimates.get(s) or {}).get("estimate")]
    tiers = [estimates[s].get("tier") for s in story_ids if (estimates.get(s) or {}).get("tier")]
    if tiers:
        top = max(tiers, key=lambda t: TIER_ORDER.index(t) if t in TIER_ORDER else -1)
        counts = {t: tiers.count(t) for t in sorted(set(tiers), key=lambda t: TIER_ORDER.index(t) if t in TIER_ORDER else 9)}
        complexity = top if len(counts) == 1 else f"{top} (mixed: " + ", ".join(f"{k} x{v}" for k, v in counts.items()) + ")"
    else:
        complexity = None
    apps = sorted({(estimates.get(s) or {}).get("application") for s in story_ids} - {None, ""})
    stacks = sorted({x.strip() for s in story_ids for x in str((estimates.get(s) or {}).get("tech_stack") or "").split(",")} - {""})
    header = {"application": application or ", ".join(apps) or project,
              "overall_complexity": complexity, "technology_stack": tech_stack or ", ".join(stacks) or None}

    flags = []
    if any(any(v.get("source") == "llm" for v in (e.get("entries") or {}).values()) for e in ests):
        flags.append("Traditional effort is LLM-estimated and unvalidated (no rate card): internal use only.")
    if any(not e.get("confirmed") for e in ests):
        flags.append("Some traditional estimates have not been confirmed by a developer.")
    if sum(1 for s in story_ids if not (estimates.get(s) or {}).get("estimate")):
        flags.append("Stories with no traditional estimate are excluded from the comparison (listed on the Details sheet).")
    cx_uncal = [s for s in story_ids if ((estimates.get(s) or {}).get("complexity") or {}).get("calibrated") is False]
    if cx_uncal:
        flags.append("Complexity model is UNCALIBRATED for some stories.")
    if unmapped_h:
        flags.append(f"{unmapped_h:.2f} h of effort sits outside any stage (unassigned/setup) and is not in the phase rows.")
    idle = sum(int(_num(r.get("idle_excluded"))) for r in scoped)
    capped = sum(int(_num(r.get("capped"))) for r in scoped)
    if idle:
        flags.append(f"{idle} approval gap(s) were EXCLUDED as idle; real review time may be higher.")
    if capped:
        flags.append(f"{capped} AI turn(s) were capped at the turn limit.")
    if tokens["total_in"] + tokens["total_out"] == 0:
        flags.append("No real token data (OpenTelemetry) in this range: token columns are blank/estimate only.")
    elif src.get("estimate") or src.get("none"):
        flags.append("Some rows have no real token data (OpenTelemetry was off for those turns).")
    return {"project": project, "date_from": date_from, "date_to": date_to, "generated_at": iso(),
            "model_version": model["model_version"], "hours_per_day": hpd, "story_count": len(story_ids),
            "stories": story_ids, "header": header, "benefits": benefits, "rows": out_rows,
            "tokens": tokens, "flags": flags, "definitions": DEFINITIONS,
            "excluded": [{"story_id": s, "phase": p, "hours": round(h, 2)} for (s, p), h in sorted(excluded.items())],
            "effort_rows": scoped}


def build(project: str, date_from: str = None, date_to: str = None, model: dict = None, cfg=None) -> dict:
    """LOCAL PREVIEW from stories cached on this machine. Not a project total if more than one
    developer worked the project: run the pipeline for that."""
    cfg = cfg or load_config()
    stories = project_stories(project)
    rows, estimates = from_stories(stories, cfg)
    res = build_report(project, rows, estimates, date_from, date_to, model, cfg)
    res["flags"].insert(0, "LOCAL PREVIEW: only stories cached on this machine. Run the ADO pipeline for the "
                           "real, all-developer figure.")
    return res


def build_from_records(project, records, fields, date_from=None, date_to=None, model=None, cfg=None,
                       application=None, tech_stack=None) -> dict:
    cfg = cfg or load_config()
    rows, estimates = from_records(records, fields, project)
    return build_report(project, rows, estimates, date_from, date_to, model, cfg, application, tech_stack)


# ---------------------------------------------------------------- markdown rendering

def markdown(result: dict) -> str:
    b = result["benefits"]

    def pct(v):
        return f"{v:.1%}" if v is not None else "NEEDS INPUT"

    rng = f"{result['date_from'] or 'start'} to {result['date_to'] or 'latest'}"
    h = result["header"]
    L = [f"## AI Productivity (AI Efficiency Report) - {result['project']}", "",
         f"_Generated {result.get('generated_at', '')} | range {rng} | {result['story_count']} stories | "
         f"model {result['model_version']}_", "",
         f"Application: **{h['application']}** | Overall complexity: **{h['overall_complexity'] or 'n/a'}** | "
         f"Technology stack: **{h['technology_stack'] or 'n/a'}**", "",
         "| Effort saving | Time saving | Cost saving | Automated completion |", "|---|---|---|---|",
         f"| {pct(b['effort_saving_pct'])} | {pct(b['time_saving_pct'])} | n/a | {pct(b['automated_completion_pct'])} |", "",
         "### Delivery comparison", "",
         "| Phase | Traditional PD | AI PD | Traditional days | AI days | Automation % | Evidence |",
         "|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        def c(v):
            return "" if v is None else v
        L.append(f"| {r['label']} | {c(r['traditional_pd'])} | {c(r['ai_pd'])} | {c(r['traditional_days'])} | "
                 f"{c(r['ai_days'])} | {pct(r['automation_pct']) if r['automation_pct'] is not None else ''} | {r['evidence']} |")
    t = result["tokens"]
    L += ["", f"Tokens in range: in {t['total_in']:,} / out {t['total_out']:,} (real, OpenTelemetry)."
          if (t["total_in"] or t["total_out"]) else "Tokens in range: no real token data.", ""]
    for f in result["flags"]:
        L.append(f"> {f}")
    return "\n".join(L) + "\n"
