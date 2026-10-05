#!/usr/bin/env python3
"""Offline demo: builds the AI Efficiency workbook from synthetic rows (no ADO, no Copilot needed).

    python .github/scripts/pipeline/demo_ai_efficiency.py [out_dir] [from_date] [to_date]

Use it to review the layout and the definitions before the real pipeline has data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from mda import benefits, xlsx  # noqa: E402


def r(story, day, stage, ai=0.0, appr=0.0, man=0.0, dev="dev1", tin=0, tout=0, agent=None):
    return {"story_id": story, "developer": dev, "work_date": day, "stage": stage, "cycle": 1,
            "ai_hours": ai, "approval_hours": appr, "manual_hours": man, "tokens_in": tin, "tokens_out": tout,
            "tokens_est": 0, "token_source": "otel" if tin else "none",
            "agents": {agent: {"in": tin, "out": tout}} if agent else {}}


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    date_from = sys.argv[2] if len(sys.argv) > 2 else None
    date_to = sys.argv[3] if len(sys.argv) > 3 else None
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        r("101", "2026-09-01", "requirements", 0.8, 0.3, tin=40_000, tout=6_000, agent="requirements-agent"),
        r("101", "2026-09-01", "discovery", 1.5, 0.4, tin=120_000, tout=15_000, agent="legacy-analyst"),
        r("101", "2026-09-02", "plan", 1.8, 0.5, tin=90_000, tout=14_000, agent="target-architect"),
        r("101", "2026-09-02", "build", 3.0, 0.6, tin=300_000, tout=60_000, agent="build-engineer"),
        r("101", "2026-09-03", "build", 3.5, 0.5, dev="dev2", tin=280_000, tout=55_000, agent="build-engineer"),
        r("101", "2026-09-03", "quality", 1.2, 0.3, tin=60_000, tout=9_000, agent="quality-gate-agent"),
        r("101", "2026-09-04", "qa_authoring", 1.0, 0.3, tin=50_000, tout=8_000, agent="qa-authoring-agent"),
        r("101", "2026-09-04", "qa_execution", man=2.0),
        r("101", "2026-09-05", "transition_to_live", man=3.0),
        r("101", "2026-09-05", "support", man=1.5),
        r("102", "2026-09-08", "discovery", 1.0, 0.2, tin=70_000, tout=9_000, agent="legacy-analyst"),
        r("102", "2026-09-09", "build", 4.5, 0.8, tin=350_000, tout=70_000, agent="build-engineer"),
    ]
    est = lambda phases: {"phases": phases, "confirmed": True,  # noqa: E731
                          "entries": {k: {"pd": v, "source": "llm", "reason": "demo"} for k, v in phases.items()}}
    ests = {
        "101": {"story_id": "101", "tier": "High", "application": "D2R2", "tech_stack": ".Net 10, AWS",
                "estimate": est({"discovery": 4.0, "design": 3.0, "build": 12.0, "test": 6.0,
                                 "transition_to_live": 3.0, "support": 2.0})},
        "102": {"story_id": "102", "tier": "Medium", "application": "D2R2", "tech_stack": ".Net 10, AWS",
                "estimate": est({"discovery": 2.0, "build": 8.0})},
    }
    result = benefits.build_report("Demo project", rows, ests, date_from, date_to)
    path = xlsx.write_workbook(result, out / "ai-efficiency-demo.xlsx")
    (out / "ai-efficiency-demo.md").write_text(benefits.markdown(result), encoding="utf-8")
    print(benefits.markdown(result))
    print("workbook:", path)


if __name__ == "__main__":
    main()
