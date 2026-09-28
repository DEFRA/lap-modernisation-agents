"""Per-developer Copilot usage (spec s7.5). Developer/subscription-level, NOT story-level.

Uses the developer's own authenticated `gh` session (self-accessible, no admin role):
  GET /users/{login}/settings/billing/premium_request/usage?year=&month=
A quick pull is a cumulative month-to-date total, not a day-by-day log; each daily snapshot is
stored so the delta between snapshots approximates daily use. Story-level token attribution
comes from the hook log, not from here. Tagged with the CONFIRMED account (s3.4) and date.
"""
from __future__ import annotations

import json
import subprocess

from .ado import AdoClient, AdoError
from .core import iso, load_config, parse_ts, read_json, store_dir, utcnow, write_json


def _gh_api(login: str, path: str) -> dict:
    env = None
    tok = subprocess.run(["gh", "auth", "token", "--user", login], capture_output=True, text=True, timeout=15)
    if tok.returncode == 0 and tok.stdout.strip():
        import os
        env = {**os.environ, "GH_TOKEN": tok.stdout.strip()}  # never printed or stored
    p = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json",
                        "-H", "X-GitHub-Api-Version: 2022-11-28", path],
                       capture_output=True, text=True, timeout=30, env=env)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip()[:300])
    return json.loads(p.stdout)


def _file(login):
    return store_dir() / "usage" / f"{login}.json"


def snapshot(login: str, fetch=_gh_api) -> dict:
    now = utcnow()
    data = fetch(login, f"/users/{login}/settings/billing/premium_request/usage?year={now.year}&month={now.month}")
    items = data.get("usageItems", [])
    total = sum(float(i.get("grossQuantity", i.get("quantity", 0)) or 0) for i in items)
    net = sum(float(i.get("netQuantity", 0) or 0) for i in items)
    by_model = {}
    for i in items:
        m = i.get("model") or i.get("sku") or "unknown"
        by_model[m] = by_model.get(m, 0) + float(i.get("grossQuantity", i.get("quantity", 0)) or 0)
    return {"login": login, "date": now.date().isoformat(), "month": f"{now.year}-{now.month:02d}",
            "taken_at": iso(now), "premium_requests_gross_mtd": total, "premium_requests_net_mtd": net,
            "by_model_mtd": by_model, "cumulative": True}


def sync(login: str, fetch=_gh_api, client=None) -> dict:
    snap = snapshot(login, fetch)
    log, _ = read_json(_file(login))
    log = log or {"login": login, "snapshots": []}
    log["snapshots"] = [s for s in log["snapshots"] if s["date"] != snap["date"]] + [snap]
    prev = [s for s in log["snapshots"] if s["month"] == snap["month"] and s["date"] < snap["date"]]
    snap["delta_since_prev_snapshot"] = round(
        snap["premium_requests_gross_mtd"] - (prev[-1]["premium_requests_gross_mtd"] if prev else 0), 3)
    write_json(_file(login), log)
    c = client or AdoClient(project=load_config()["ado"]["project"] or "")
    pushed = False
    if c.configured:
        try:
            key = f"MDA-usage-{login}-{snap['date']}"
            c.upsert_record(key, {"project": "(developer-usage)", "stage": "usage", "phase": "dev",
                                  "developer": login, "tokens": int(snap["premium_requests_gross_mtd"]),
                                  "recorded_at": iso()}, json.dumps(snap))
            pushed = True
        except AdoError as e:
            snap["push_error"] = str(e)
    return {"snapshot": snap, "pushed_to_ado": pushed}


def maybe_daily_sync(story) -> None:
    """Opportunistic 'daily' cadence: runs at session start when the last snapshot is old."""
    if not story:
        return
    login = story["setup"].get("account", {}).get("confirmed_login")
    if not login:
        return
    log, _ = read_json(_file(login))
    hrs = load_config()["usage"]["sync_every_hours"]
    if log and log["snapshots"]:
        last = parse_ts(log["snapshots"][-1]["taken_at"])
        if (utcnow() - last).total_seconds() < hrs * 3600:
            return
    sync(login)
