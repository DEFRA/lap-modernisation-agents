"""Effort/token/complexity report (spec s7.3, s8, s9, s11 Wiki narrative)."""
from __future__ import annotations

from . import effort as E
from .complexity import load_model
from .core import iso, load_config


def _h(sec):
    return f"{sec / 3600:.2f} h"


def build(story: dict, cfg=None) -> dict:
    cfg = cfg or load_config()
    tot = E.story_totals(story)
    hpd = cfg["effort"]["hours_per_day"]
    cx = (story.get("complexity") or {}).get("result")
    dev_h = tot["active_seconds_by_phase"]["dev"] / 3600
    eff = None
    if cx:
        trad_h = cx["traditional_days"]["point"] * hpd
        eff = {"traditional_days_point": cx["traditional_days"]["point"],
               "measured_agentic_dev_days": round(dev_h / hpd, 2),
               "measured_efficiency": round(1 - dev_h / trad_h, 3) if trad_h else None,
               "assumed_efficiency_for_tier": cx["efficiency_assumed"],
               "baseline_efficiency": cx["baseline_efficiency"]}
    return {"generated_at": iso(), "project": story["project"], "story_id": story["story_id"],
            "cycle": story["cycle"], "complete": story["complete"], "closed": story["closed"],
            "totals": tot, "rows": list(E.rollup(story).values()), "sprints": E.by_sprint(story, cfg),
            "complexity": cx, "efficiency": eff, "anomalies": story.get("anomalies", [])[-20:],
            "capped_entries": sum(1 for x in story["effort"] if x.get("capped"))}


def markdown(story: dict, cfg=None) -> str:
    r = build(story, cfg)
    t = r["totals"]
    L = [f"## Effort report - story {r['story_id']} ({r['project']}) - {r['generated_at'][:10]}", ""]
    cx = r["complexity"]
    if cx and not cx.get("calibrated"):
        L += ["> **UNCALIBRATED complexity model - internal use only, not client-facing (spec s8.3/s15).**", ""]
    L += [f"Cycle: {r['cycle']} | Dev-complete: {r['complete']} | QA-closed: {r['closed']}", "",
          "### Effort (active work) vs calendar duration", "",
          "| Measure | Value |", "|---|---|",
          f"| Active effort - dev (AI-assisted) | {_h(t['active_seconds_by_phase']['dev'])} |",
          f"| Active effort - QA authoring (AI-assisted) | {_h(t['active_seconds_by_phase']['qa-authoring'])} |",
          f"| Active effort - QA manual execution (no AI; no efficiency claim) | {_h(t['active_seconds_by_phase']['qa-execution'])} |",
          f"| **Total active effort** | **{_h(t['active_seconds_total'])}** |",
          f"| Calendar duration (elapsed) | {_h(t['calendar_seconds'])} |",
          f"| Estimated prompt tokens (story, from hook log) | {t['tokens_est']:,} |", ""]
    L += ["### By cycle / stage", "", "| Cycle | Stage | Phase | Trigger | AI | Approval | Manual | Active |",
          "|---|---|---|---|---|---|---|---|"]
    for x in sorted(r["rows"], key=lambda z: (z["cycle"], z["stage"])):
        L.append(f"| {x['cycle']} | {x['stage']} | {x['phase']} | {x.get('trigger') or '-'} | "
                 f"{_h(x['ai_seconds'])} | {_h(x['approval_seconds'])} | {_h(x['manual_seconds'])} | "
                 f"{_h(x['active_seconds'])}{' *' if x['capped'] else ''} |")
    if r["capped_entries"]:
        L += ["", f"\\* {r['capped_entries']} interval(s) hit the idle cap and were truncated."]
    L += ["", "### By sprint", "", "| Sprint | Dev | QA authoring | QA execution |", "|---|---|---|---|"]
    for sp, b in r["sprints"].items():
        L.append(f"| {sp} | {_h(b['dev'])} | {_h(b['qa-authoring'])} | {_h(b['qa-execution'])} |")
    if cx:
        L += ["", "### Complexity", "", f"Model `{cx['model_version']}` (calibrated: {cx['calibrated']}). "
              f"Score **{cx['score']}** -> tier **{cx['tier']}**; traditional estimate "
              f"{cx['traditional_days']['low']}-{cx['traditional_days']['high'] or '+'} days.", "",
              "| Factor | Count | Weight | Points |", "|---|---|---|---|"]
        for k, n in cx["counts"].items():
            L.append(f"| {k} | {n} | {cx['weights'][k]} | {cx['points_by_factor'][k]} |")
        if cx.get("developer_adjustment"):
            L.append(f"\nDeveloper adjusted tier: {cx['developer_adjustment']['from_tier']} -> "
                     f"{cx['developer_adjustment']['to_tier']} ({cx['developer_adjustment']['note']})")
    e = r["efficiency"]
    if e:
        L += ["", "### Efficiency (dev phase only)", "",
              f"Measured: **{e['measured_efficiency']:.0%}** vs tier assumption {e['assumed_efficiency_for_tier']:.0%} "
              f"(programme baseline ~{e['baseline_efficiency']:.0%}, +/- a little; the remaining ~60% is manual by design: "
              "approvals, review, PR, manual QA, Sonar/review triage). Anchor assumption, not a measured fact, until calibrated."
              if e["measured_efficiency"] is not None else "Insufficient data."]
    return "\n".join(L) + "\n"
