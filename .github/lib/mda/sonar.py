"""SonarCloud integration for /fix-sonar (spec s10.1) using the public/anonymous API.

Order: quality-gate status/measures (reliable) -> issue detail -> fallback to the PR check
annotations when the PR-scoped issue search is empty although the gate shows violations.
Anonymous calls may be rate-limited; verify under real volume (spec s15).
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from .core import load_config

METRICS = "new_violations,new_bugs,new_vulnerabilities,new_code_smells,new_coverage,new_duplicated_lines_density,new_security_hotspots"


def _get(url: str, timeout=15):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:300]}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"error": str(e)}


def gh_annotations(pr: int, run=subprocess.run) -> list:
    """Fallback: SonarCloud posts its PR decoration as GitHub check-run annotations."""
    def gh(*a):
        p = run(["gh", *a], capture_output=True, text=True, timeout=30)
        return json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else None
    pr_info = gh("pr", "view", str(pr), "--json", "headRefOid")
    repo = gh("repo", "view", "--json", "nameWithOwner")
    if not pr_info or not repo:
        return []
    runs = gh("api", f"repos/{repo['nameWithOwner']}/commits/{pr_info['headRefOid']}/check-runs") or {}
    out = []
    for cr in runs.get("check_runs", []):
        if "sonar" not in (cr.get("name", "") + (cr.get("app") or {}).get("slug", "")).lower():
            continue
        for a in gh("api", f"repos/{repo['nameWithOwner']}/check-runs/{cr['id']}/annotations") or []:
            out.append({"path": a.get("path"), "line": a.get("start_line"), "level": a.get("annotation_level"),
                        "message": a.get("message"), "title": a.get("title"), "source": "github-annotation"})
    return out


def fetch_pr(pr: int, cfg=None, get=_get, annotations=gh_annotations) -> dict:
    cfg = cfg or load_config()
    s = cfg["sonar"]
    if not (s["organization"] and s["project_key"]):
        return {"ok": False, "reason": "sonar organization/project_key not configured "
                                       "(sonar.organization / sonar.project_key)"}
    host, org, key = s["host"].rstrip("/"), s["organization"], s["project_key"]
    q = urllib.parse.urlencode
    st, gate = get(f"{host}/api/qualitygates/project_status?" + q({"projectKey": key, "pullRequest": pr}))
    if st != 200:
        return {"ok": False, "reason": f"quality gate call failed ({st}): {gate.get('error')}",
                "hint": "rate limit or non-public project? fall back to annotations"}
    st_m, meas = get(f"{host}/api/measures/component?" + q({"component": key, "pullRequest": pr, "metricKeys": METRICS}))
    st_i, iss = get(f"{host}/api/issues/search?" + q({
        "componentKeys": key, "pullRequest": pr, "organization": org, "resolved": "false", "ps": 200}))
    issues = [{"key": i.get("key"), "rule": i.get("rule"), "severity": i.get("severity"),
               "type": i.get("type"), "path": i.get("component", "").split(":", 1)[-1],
               "line": i.get("line"), "message": i.get("message"), "source": "sonar-api"}
              for i in (iss.get("issues", []) if st_i == 200 else [])]
    gate_status = gate.get("projectStatus", {}).get("status")
    failed = [c for c in gate.get("projectStatus", {}).get("conditions", []) if c.get("status") == "ERROR"]
    fallback = False
    if not issues and gate_status == "ERROR":
        # Known caveat: PR-scoped issue search can be empty while the gate is failing.
        issues, fallback = annotations(pr), True
    return {"ok": True, "gate_status": gate_status, "failed_conditions": failed,
            "measures": (meas.get("component", {}).get("measures", []) if st_m == 200 else []),
            "issues": issues, "used_annotation_fallback": fallback,
            "empty_but_failing": bool(gate_status == "ERROR" and not issues)}
