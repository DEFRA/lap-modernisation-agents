#!/usr/bin/env python3
"""ADO Pipeline step (spec s13): query Effort Records -> Excel artifact -> APPEND a Wiki entry.

Env (set by the pipeline): MDA_ADO_ORG_URL, MDA_ADO_PROJECT, MDA_ADO_PAT (or SYSTEM_ACCESSTOKEN),
BUILD_ID, OUT_DIR. The pipeline identity needs Wiki *edit* permission in addition to work-item
read; Analytics/work-item scopes do not cover wiki writes.
"""
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from mda.ado import AdoClient  # noqa: E402
from mda.core import iso, load_config  # noqa: E402


def fetch_records(c: AdoClient):
    tag = c.cfg["ado"]["record_tag"]
    ids = c.wiql(f"Select [System.Id] From WorkItems Where [System.Tags] Contains '{tag}'")
    rows = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        res, _ = c.request("GET", c._p("wit/workitems", ids=",".join(map(str, chunk)), **{"$expand": "none"}))
        rows += [w["fields"] for w in res.get("value", [])]
    return rows


def to_frames(records, fields):
    import pandas as pd
    inv = {v: k for k, v in fields.items()}
    flat = []
    for r in records:
        title = r.get("System.Title", "")
        row = {inv[k]: v for k, v in r.items() if k in inv and k != "payload"}
        if "stage" not in row:  # payload-only fallback records
            try:
                desc = r.get("System.Description", "").replace("<pre>", "").replace("</pre>", "")
                row.update(json.loads(desc.replace("&lt;", "<").replace("&amp;", "&")))
            except ValueError:
                pass
        row["record_key"] = title
        flat.append(row)
    df = pd.DataFrame(flat)
    if df.empty:
        return {"Effort Rows": df}
    rows = df[~df["record_key"].str.contains("-state$|^MDA-usage-", regex=True)]
    usage = df[df["record_key"].str.startswith("MDA-usage-")]
    ai = rows[rows["phase"] != "qa-execution"]
    qa_manual = rows[rows["phase"] == "qa-execution"]  # reported separately - no AI-efficiency claim
    summary = (ai.groupby(["project", "story_id"], dropna=False)
                 .agg(tier=("tier", "last"), traditional_days=("traditional_days", "last"),
                      active_effort_hours=("effort_hours", "sum"), tokens=("tokens", "sum"),
                      cycles=("cycle", "max")).reset_index())
    return {"Effort Rows": rows, "Story Summary": summary, "QA Manual Execution": qa_manual,
            "Developer Usage": usage}


def main():
    c = AdoClient(project=os.environ.get("MDA_ADO_PROJECT"))
    if not c.configured:
        sys.exit("ADO not configured (MDA_ADO_ORG_URL / MDA_ADO_PROJECT / MDA_ADO_PAT)")
    out_dir = Path(os.environ.get("OUT_DIR", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = to_frames(fetch_records(c), c.cfg["ado"]["fields"])
    xlsx = out_dir / f"migration-effort-{iso()[:10]}.xlsx"
    import pandas as pd
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        for name, df in frames.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    build = os.environ.get("BUILD_ID", "")
    link = (f"{c.org}/{urllib.parse.quote(c.project)}/_build/results?buildId={build}&view=artifacts"
            if build else "(artifact link unavailable)")
    entry = (f"### Effort export {iso()[:16]}Z\n\n[Download {xlsx.name}]({link}) - requires ADO sign-in with "
             f"project access (not a public link).\n\nRows: {sum(len(f) for f in frames.values())}")
    print(json.dumps(c.wiki_append(load_config()["ado"]["wiki_report_path"], entry)))  # append, never replace


if __name__ == "__main__":
    main()
