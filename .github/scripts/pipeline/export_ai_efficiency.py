#!/usr/bin/env python3
"""ADO pipeline step: the AI Productivity (AI Efficiency) Excel report for a date range.

Reads every developer's synced Effort Records for ONE ADO project (each team runs the pipeline in
its own project), filters by WORK date, aggregates, writes an .xlsx (+ markdown) and optionally
appends a summary to the ADO Wiki. No dates = all data.

Env (set by the pipeline): MDA_ADO_ORG_URL, MDA_ADO_PROJECT, SYSTEM_ACCESSTOKEN (or MDA_ADO_PAT),
OUT_DIR, and optionally FROM_DATE, TO_DATE (YYYY-MM-DD, inclusive), STORY_IDS (comma list),
APPLICATION, TECH_STACK (header overrides), REPORT_PROJECT (defaults to MDA_ADO_PROJECT),
APPEND_WIKI (true/false), BUILD_ID.
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from mda import benefits, xlsx  # noqa: E402
from mda.ado import AdoClient  # noqa: E402
from mda.core import iso, load_config  # noqa: E402


def parse_date(name, value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        sys.exit(f"{name} must be YYYY-MM-DD, got {value!r}")


def fetch_records(c: AdoClient):
    """Every work item tagged MDA-EffortRecord in the project, all developers."""
    tag = c.cfg["ado"]["record_tag"]
    ids = c.wiql(f"Select [System.Id] From WorkItems Where [System.Tags] Contains '{tag}'")
    rows = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        res, _ = c.request("GET", c._p("wit/workitems", ids=",".join(map(str, chunk)), **{"$expand": "none"}))
        rows += [w["fields"] for w in res.get("value", [])]
    return rows


def main():
    date_from = parse_date("FROM_DATE", os.environ.get("FROM_DATE"))
    date_to = parse_date("TO_DATE", os.environ.get("TO_DATE"))
    if date_from and date_to and date_from > date_to:
        sys.exit(f"FROM_DATE {date_from} is after TO_DATE {date_to}")
    c = AdoClient(project=os.environ.get("MDA_ADO_PROJECT"))
    if not c.configured:
        sys.exit("ADO not configured (MDA_ADO_ORG_URL / MDA_ADO_PROJECT / token)")
    project = os.environ.get("REPORT_PROJECT") or c.project
    out_dir = Path(os.environ.get("OUT_DIR", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)

    records = fetch_records(c)
    rows, estimates = benefits.from_records(records, c.cfg["ado"]["fields"], project)
    wanted = {s.strip() for s in os.environ.get("STORY_IDS", "").split(",") if s.strip()}
    if wanted:
        rows = [r for r in rows if str(r["story_id"]) in wanted]
        estimates = {k: v for k, v in estimates.items() if k in wanted}
    result = benefits.build_report(project, rows, estimates, date_from, date_to,
                                   application=os.environ.get("APPLICATION") or None,
                                   tech_stack=os.environ.get("TECH_STACK") or None)

    stamp = f"{date_from or 'all'}_{date_to or 'all'}"
    xlsx_path = xlsx.write_workbook(result, out_dir / f"ai-efficiency-{project}-{stamp}.xlsx".replace(" ", "_"))
    (out_dir / "ai-efficiency.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    md = benefits.markdown(result)
    (out_dir / "ai-efficiency.md").write_text(md, encoding="utf-8")

    summary = {"ok": True, "records_seen": len(records), "effort_rows": len(rows), "stories": result["story_count"],
               "date_from": date_from, "date_to": date_to, "xlsx": xlsx_path.name, "flags": result["flags"],
               "generated_at": iso()}
    if os.environ.get("APPEND_WIKI", "").lower() == "true":
        build = os.environ.get("BUILD_ID", "")
        link = (f"{c.org}/{urllib.parse.quote(c.project)}/_build/results?buildId={build}&view=artifacts"
                if build else "(artifact link unavailable)")
        entry = md + f"\n[Download {xlsx_path.name}]({link}) - requires ADO sign-in with project access.\n"
        summary["wiki"] = c.wiki_append(load_config()["ado"]["wiki_report_path"] + "/AI-Efficiency", entry)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
