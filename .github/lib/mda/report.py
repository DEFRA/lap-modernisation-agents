"""Effort/token/complexity report (spec s7.3, s8, s9, s11 Wiki narrative)."""
from __future__ import annotations

from . import effort as E
from .core import iso, load_config
from .state import STAGES

PHASE_LINES = [
    ("dev", "Active effort - dev (AI-assisted)"),
    ("qa-authoring", "Active effort - QA authoring (AI-assisted)"),
    ("qa-execution", "Active effort - QA manual execution (no AI; no efficiency claim)"),
    ("transition_to_live", "Active effort - Transition to Live (manual entry)"),
    ("support", "Active effort - Support (manual entry)"),
    ("unassigned", "Active effort - outside any stage (not counted as dev)"),
]


def _h(sec):
    return f"{sec / 3600:.2f} h"


def _stage_order(stage):
    return STAGES.index(stage) if stage in STAGES else len(STAGES) + (0 if stage == "unassigned" else 1)


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
    rows = sorted(E.rollup(story).values(), key=lambda z: (z["cycle"], _stage_order(z["stage"])))
    return {"generated_at": iso(), "project": story["project"], "story_id": story["story_id"],
            "cycle": story["cycle"], "complete": story["complete"], "closed": story["closed"],
            "application": story["setup"].get("application"), "tech_stack": story["setup"].get("tech_stack"),
            "totals": tot, "rows": rows, "sprints": E.by_sprint(story, cfg),
            "complexity": cx, "estimate": story.get("estimate"), "efficiency": eff,
            "anomalies": story.get("anomalies", [])[-20:],
            "capped_entries": sum(1 for x in story["effort"] if x.get("capped") and not x.get("idle_excluded")),
            "idle_excluded_entries": sum(1 for x in story["effort"] if x.get("idle_excluded")),
            "otel": story.get("otel")}


def _tokens_line(t, otel):
    if t["tokens_in"] or t["tokens_out"]:
        return (f"| Tokens (real, Copilot OpenTelemetry) | in {t['tokens_in']:,} / out {t['tokens_out']:,} "
                f"/ total {t['tokens_in'] + t['tokens_out']:,} |")
    why = "no OpenTelemetry file imported yet" if not otel else "OpenTelemetry file had no token data for this story"
    return (f"| Tokens (real) | **UNAVAILABLE** - {why} (see docs/mda/otel-setup.md). "
            f"Prompt-size estimate only: {t['tokens_est']:,} (typed prompt chars / 4; not usage) |")


def markdown(story: dict, cfg=None) -> str:
    r = build(story, cfg)
    t = r["totals"]
    L = [f"## Effort report - story {r['story_id']} ({r['project']}) - {r['generated_at'][:10]}", ""]
    cx = r["complexity"]
    est = r["estimate"]
    if cx and not cx.get("calibrated"):
        L += ["> **UNCALIBRATED complexity model - internal use only, not client-facing (spec s8.3/s15).**", ""]
    if est and est.get("labels"):
        L += [f"> Traditional estimate: {'; '.join(est['labels'])}.", ""]
    L += [f"Cycle: {r['cycle']} | Dev-complete: {r['complete']} | QA-closed: {r['closed']}", "",
          "### Effort (active work) vs calendar duration", "",
          "| Measure | Value |", "|---|---|"]
    for key, label in PHASE_LINES:
        sec = t["active_seconds_by_phase"].get(key, 0.0)
        if sec or key in ("dev", "qa-authoring", "qa-execution"):
            L.append(f"| {label} | {_h(sec)} |")
    L += [f"| **Total active effort** | **{_h(t['active_seconds_total'])}** |",
          f"| Calendar duration (elapsed) | {_h(t['calendar_seconds'])} |",
          _tokens_line(t, r["otel"]), ""]
    L += ["### By cycle / stage", "", "| Cycle | Stage | Phase | Trigger | AI | Approval | Manual | Active | Tokens in/out |",
          "|---|---|---|---|---|---|---|---|---|"]
    for x in r["rows"]:
        tok = f"{x['tokens_in']:,} / {x['tokens_out']:,}" if (x["tokens_in"] or x["tokens_out"]) else "-"
        L.append(f"| {x['cycle']} | {x['stage']} | {x['phase']} | {x.get('trigger') or '-'} | "
                 f"{_h(x['ai_seconds'])} | {_h(x['approval_seconds'])} | {_h(x['manual_seconds'])} | "
                 f"{_h(x['active_seconds'])}{' *' if x['capped'] else ''} | {tok} |")
    if r["capped_entries"]:
        L += ["", f"\\* {r['capped_entries']} AI turn(s) hit the turn cap and were truncated."]
    if r["idle_excluded_entries"]:
        L += ["", f"{r['idle_excluded_entries']} approval gap(s) exceeded the idle limit and were EXCLUDED "
                  "(developer assumed away); real review time for those may be higher."]
    phases = [p for p, _ in PHASE_LINES]
    L += ["", "### By sprint", "", "| Sprint | " + " | ".join(phases) + " |", "|---|" + "---|" * len(phases)]
    for sp, b in r["sprints"].items():
        L.append(f"| {sp} | " + " | ".join(_h(b.get(p, 0.0)) for p in phases) + " |")
    if est:
        L += ["", "### Traditional estimate (person-days, LLM-estimated)", "",
              f"Method `{est['method']}` | "
              f"{'confirmed by ' + str(est.get('confirmed_by')) if est.get('confirmed') else 'NOT confirmed'}", "",
              "| Phase | PD | Source | Reason |", "|---|---|---|---|"]
        for ph in ("discovery", "design", "build", "test", "transition_to_live", "support"):
            e_ = (est.get("entries") or {}).get(ph)
            L.append(f"| {ph} | {e_['pd'] if e_ else 'NEEDS INPUT'} | {(e_ or {}).get('source', '')} | "
                     f"{(e_ or {}).get('reason', '')} |")
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
