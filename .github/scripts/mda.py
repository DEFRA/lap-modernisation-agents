#!/usr/bin/env python3
"""mda - Migration Delivery Agent CLI. Every subcommand prints one JSON document.

There is deliberately NO subcommand that approves a gate: approval is recorded only by the
userPromptSubmitted hook from what the developer types, so an agent cannot approve its own work.
Exit codes: 0 ok, 2 bad input, 3 blocked (setup incomplete / prerequisite / PAT).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from mda import __version__  # noqa: E402
from mda import complexity as C  # noqa: E402
from mda import effort as E  # noqa: E402
from mda import benefits, estimate as EST, identity, manual, metrics, otel, report as R, sonar  # noqa: E402
from mda import state as S, sync, usage  # noqa: E402
from mda.ado import AdoClient, AdoError, known_projects  # noqa: E402
from mda.core import iso, load_config, parse_ts, repo_root, utcnow  # noqa: E402


def out(obj, code=0):
    print(json.dumps(obj, indent=2, default=str))
    sys.exit(code)


def ctx(args, need_story=True):
    sid, reliable = S.resolve_session_id({"sessionId": getattr(args, "session_id", None)})
    sess = S.load_session(sid)
    story = None
    if sess.get("story_id"):
        story, st = S.load_story(sess["story_id"])
        if st == "corrupt":
            story, why = sync.recover(sess["story_id"])
            if story:
                sync.save_story_clean(story)
            elif need_story:
                out({"ok": False, "reason": "local_cache_corrupt", "recovery": why,
                     "message": "Local cache corrupt and ADO recovery failed; ask the developer."}, 3)
    if need_story and not story:
        out({"ok": False, "reason": "no_story_bound", "local_stories": S.list_local_stories(),
             "message": "No story bound to this session. Run setup (or `story resume --id N`)."}, 3)
    return sid, sess, story


def persist(sess, story, reason=None, push=False):
    res = None
    if push and story:
        res = sync.push(story, reason or "cli")
        if res.get("ok"):
            sync.save_story_clean(story)
        else:
            S.save_story(story)
    elif story:
        S.save_story(story)
    S.save_session(sess)
    return res


# ------------------------------------------------------------------ setup

def cmd_setup(a):
    sid, sess, story = ctx(a, need_story=False)
    if a.sub == "status":
        miss = S.setup_missing(story)
        out({"ok": not miss, "session_id": sid, "story_id": (story or {}).get("story_id"),
             "missing": miss, "auto_continue": (story or {}).get("setup", {}).get("auto_continue", False), "local_stories": S.list_local_stories(),
             "hold": bool(miss), "instruction": "Ask for every missing item and HOLD all pipeline work." if miss else ""})
    if a.sub == "prereqs":
        out({"ok": True, **identity.prerequisites()})
    if a.sub == "pat":
        c = AdoClient(project=(story or {}).get("project") or load_config()["ado"]["project"] or "x")
        res = identity.check_pat(c if c.pat and c.org else None)
        if story is not None:
            story["setup"]["pat"] = {"status": res["status"], "checked_at": iso(), "days_left": res.get("days_left")}
            persist(sess, story)
        out(res, 3 if res["status"] == "blocked" else 0)
    if a.sub == "accounts":
        out({"ok": True, **identity.detect_accounts()})
    if a.sub == "set":
        if not story:
            if not (a.project and a.story_id):
                out({"ok": False, "reason": "--project and --story-id are required for a new story"}, 2)
            existing, st = S.load_story(a.story_id)
            story = existing if st == "ok" else None
            if story is None and st == "missing":
                story, why = sync.recover(a.story_id, project=a.project)   # resume from ADO if present
                if story:
                    sync.save_story_clean(story)
            if story is None:
                story = S.new_story(a.project, a.story_id)
            sess["story_id"] = story["story_id"]
        if a.project:
            allowed = known_projects(load_config())
            if allowed and a.project.strip().lower() not in [x.lower() for x in allowed]:
                out({"ok": False, "reason": "unknown_ado_project", "allowed": allowed,
                     "message": "Project must be one of the configured ADO projects (config ado.projects)."}, 2)
            story["project"] = a.project
        if a.application:
            story["setup"]["application"] = a.application
        if a.tech_stack:
            story["setup"]["tech_stack"] = a.tech_stack
        if a.migration is not None:
            story["setup"]["is_migration"] = (a.migration == "yes")
        for k in ("old", "new", "hld", "hlsa", "lld"):
            v = getattr(a, k)
            if v:
                if not Path(v).exists():
                    out({"ok": False, "reason": f"path for --{k} does not exist: {v}"}, 2)
                story["setup"]["paths"][k] = str(Path(v))
        if a.auto_continue is not None:
            story["setup"]["auto_continue"] = (a.auto_continue == "yes")
        persist(sess, story)
        out({"ok": True, "missing": S.setup_missing(story), "story_id": story["story_id"],
             "project": story["project"], "application": story["setup"].get("application"),
             "tech_stack": story["setup"].get("tech_stack"),
             "auto_continue": story["setup"].get("auto_continue", False)})
    if a.sub == "otel":
        res = otel.check()
        if story is not None:
            res["story_import"] = otel.import_into_story(story, force=True)
            persist(sess, story)
        out(res, 0 if res.get("ok") else 3)
    if a.sub == "confirm-account":
        if not story:
            out({"ok": False, "reason": "bind the story first (setup set)"}, 3)
        det = identity.detect_accounts()
        if a.login not in det["candidates"] and not a.force_unlisted:
            out({"ok": False, "reason": "login not among detected accounts", "candidates": det["candidates"]}, 2)
        story["setup"]["account"] = {"confirmed_login": a.login, "confirmed_at": iso(),
                                     "copilot_cli_detected": det["copilot_cli"].get("login"),
                                     "candidates": det["candidates"]}
        persist(sess, story, "setup-complete", push=not S.setup_missing(story))
        out({"ok": True, "confirmed": a.login, "missing": S.setup_missing(story)})


# ------------------------------------------------------------------ story

def cmd_story(a):
    sid, sess, story = ctx(a, need_story=a.sub not in ("resume", "list", "recover"))
    if a.sub == "list":
        out({"ok": True, "stories": S.list_local_stories(), "bound": sess.get("story_id")})
    if a.sub in ("resume", "recover"):
        s, st = S.load_story(a.id)
        if st != "ok" or a.sub == "recover":
            s, why = sync.recover(a.id, project=a.project)
            if not s:
                out({"ok": False, "reason": why}, 3)
            sync.save_story_clean(s)
        sess["story_id"] = str(a.id)
        S.save_session(sess)
        out({"ok": True, "story_id": str(a.id), "missing_setup": S.setup_missing(s),
             "stages": {k: v["status"] for k, v in s["stages"].items()}, "cycle": s["cycle"]})
    if a.sub == "status":
        out({"ok": True, "story_id": story["story_id"], "project": story["project"], "cycle": story["cycle"],
             "complete": story["complete"], "closed": story["closed"],
             "trigger": story.get("current_trigger"), "pr": story["pr"],
             "auto_continue": story["setup"].get("auto_continue", False),
             "next_auto_stage": S.next_auto_stage(story),
             "stages": {k: v["status"] for k, v in story["stages"].items()},
             "sync": {k: story["sync"][k] for k in ("revision", "last_sync", "dirty")}})
    if a.sub == "ado-summary":
        c = AdoClient(project=story["project"])
        try:
            out({"ok": True, "story": c.story_summary(story["story_id"])})
        except AdoError as e:
            out({"ok": False, "reason": str(e)}, 3)
    if a.sub == "pr-raised":
        story["pr"].update({"raised": True, "url": a.url, "number": a.number})
        persist(sess, story)
        out({"ok": True, "next": "Ask the developer: is this story complete from a dev perspective? "
                                 "(then `story complete --answer yes|no`)"})
    if a.sub == "complete":
        r = S.mark_complete(story, a.answer == "yes")
        persist(sess, story, "story-complete-checkpoint", push=True)
        out(r, 0 if r["ok"] else 3)
    if a.sub == "reopen":
        r = S.reopen(story, a.trigger, a.reason or "")
        if r["ok"]:
            sess["trigger"] = a.trigger
        persist(sess, story, f"reopen:{a.trigger}", push=True)
        out(r, 0 if r["ok"] else 3)


# ------------------------------------------------------------------ stage & gate

def cmd_stage(a):
    sid, sess, story = ctx(a)
    if a.sub == "start":
        r = S.start_stage(story, a.stage, a.trigger)
        if not r["ok"]:
            out(r, 3)
        sess.update({"active_stage": a.stage, "stage_run_open": True, "forced": {}, "trigger": r["trigger"]})
        persist(sess, story)
        out({**r, "artifact_path": str(S.artifact_path(story["story_id"], a.stage)),
             "paths": story["setup"]["paths"]})
    if a.sub == "wait-input":
        sess["stage_run_open"] = False
        if sess.get("active_stage"):
            S.log_stage_event(story, sess["active_stage"], "wait")
        persist(sess, story)
        out({"ok": True, "note": "Ask the developer your question now; resume the stage after they reply."})
    if a.sub == "resume":
        if story["stages"][a.stage]["status"] == "in_progress":
            sess.update({"active_stage": a.stage, "stage_run_open": True})
            S.log_stage_event(story, a.stage, "resume")
            persist(sess, story)
            out({"ok": True})
        out({"ok": False, "reason": "stage not in_progress"}, 3)


def cmd_gate(a):
    sid, sess, story = ctx(a)
    if a.sub == "status":
        out({"ok": True, "awaiting": S.awaiting_stage(story),
             "stages": {k: v["status"] for k, v in story["stages"].items()}})
    if a.sub == "submit":
        r = S.submit_stage(story, a.stage, a.summary or "", require_artifact=not a.no_artifact)
        if not r["ok"]:
            out(r, 3)
        sess["stage_run_open"] = False
        res = persist(sess, story, f"gate:{a.stage}:submitted", push=True)
        out({**r, "sync": res, "instruction": (
            f"STOP. Present the {a.stage} result to the developer and wait. They approve by replying "
            "'approve' or 'request changes: <text>'. You cannot approve on their behalf.")})


# ------------------------------------------------------------------ complexity

def cmd_complexity(a):
    if a.sub == "calibrate":
        try:
            res = C.calibrate(a.history)
        except (ValueError, OSError) as e:
            out({"ok": False, "reason": str(e)}, 2)
        if a.accept:
            m = res["proposed_model"]
            m["calibrated"] = True
            m["calibration_note"] = f"Calibrated {iso()[:10]} against {res['fit']['n']} stories; R2={res['fit']['r_squared']}."
            (repo_root() / C.MODEL_PATH).write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
            res["accepted"] = True
        out({"ok": True, **res, "accepted": bool(a.accept)})
    sid, sess, story = ctx(a)
    cx = story["complexity"]
    if a.sub == "counts":     # Legacy Analyst, /discover
        try:
            cx["counts"] = C.validate_counts(json.loads(a.json), C.load_model())
        except (ValueError, TypeError) as e:
            out({"ok": False, "reason": str(e)}, 2)
        persist(sess, story)
        out({"ok": True, "counts": cx["counts"]})
    if a.sub == "score":      # Target Architect, /plan
        if not cx.get("counts"):
            out({"ok": False, "reason": "no factor counts; run /discover first"}, 3)
        cx["result"] = C.score(cx["counts"])
        cx["confirmed"] = False
        persist(sess, story)
        out({"ok": True, "result": cx["result"], "estimate": story.get("estimate"),
             "next": "Now propose the traditional estimate (PD per phase, a reason each) with "
                     "`estimate set --json ... --source llm`, using the tier's traditional_days range as a "
                     "sanity anchor. The developer confirms or adjusts the tier AND the estimate at the plan gate.",
             "present_at_gate": "Tier, score breakdown and the per-phase estimate table with its labels."})
    if a.sub == "adjust":
        cx["result"] = C.apply_override(cx["result"], a.tier, a.note)
        persist(sess, story)
        out({"ok": True, "result": cx["result"]})
    if a.sub == "confirm":
        cx["confirmed"] = True
        persist(sess, story, "complexity-confirmed", push=True)
        out({"ok": True})


# ------------------------------------------------------------------ QA

def cmd_qa(a):
    sid, sess, story = ctx(a)
    if a.sub == "log-execution":
        now = utcnow()
        start = now.timestamp() - a.minutes * 60
        E.add_entry(story, session_id=sid, stage="qa_execution", kind="manual", start=start, end=now,
                    note=a.note or "manual QA execution (no AI)")
        story["stages"]["qa_execution"]["status"] = "in_progress"
        persist(sess, story, "qa-execution-logged")
        out({"ok": True, "minutes": a.minutes, "note": "Reported as a separate line; no AI-efficiency claim."})
    if a.sub == "outcome":
        r = S.qa_outcome(story, a.result, a.reason or "")
        persist(sess, story, f"qa-outcome:{a.result}", push=True)
        out(r, 0 if r["ok"] else 3)


# ------------------------------------------------------------------ misc

def cmd_benefits(a):
    """LOCAL PREVIEW (this machine's cached stories only). The real, all-developer, date-ranged
    report is the ADO pipeline (mda-ai-efficiency-report.yml); it uses the same code."""
    try:
        result = benefits.build(a.project, a.date_from, a.date_to)
    except ValueError as e:
        out({"ok": False, "reason": str(e)}, 2)
    out_dir = repo_root() / "docs" / "mda" / "_programme" / a.project.replace("/", "-")
    out_dir.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in result.items() if k != "effort_rows"}
    (out_dir / "ai-efficiency-preview.json").write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    md = benefits.markdown(result)
    (out_dir / "ai-efficiency-preview.md").write_text(md, encoding="utf-8")
    res = {"ok": True, "preview_only": True, **slim, "markdown": md if a.print else None}
    if a.xlsx:
        from mda import xlsx
        res["xlsx"] = str(xlsx.write_workbook(result, out_dir / "ai-efficiency-preview.xlsx"))
    out(res)


def cmd_estimate(a):
    sid, sess, story = ctx(a)
    me = (story["setup"].get("account") or {}).get("confirmed_login") or "unknown"
    counts = (story["complexity"] or {}).get("counts")
    try:
        if a.sub == "set":
            if a.json:
                try:
                    items = json.loads(a.json)
                except ValueError as e:
                    out({"ok": False, "reason": f"--json is not valid JSON: {e}"}, 2)
                story["estimate"] = EST.set_many(story.get("estimate"), items, a.source, counts)
            else:
                if a.phase is None or a.pd is None:
                    out({"ok": False, "reason": "give --phase, --pd and --reason (or --json for several phases)"}, 2)
                story["estimate"] = EST.set_phase(story.get("estimate"), a.phase, a.pd, a.reason or "", a.source, counts)
        elif a.sub == "confirm":
            if not story.get("estimate"):
                out({"ok": False, "reason": "nothing to confirm; run `estimate set` first"}, 3)
            story["estimate"] = EST.confirm(story["estimate"], me)
    except (ValueError, OSError) as e:
        out({"ok": False, "reason": str(e)}, 2)
    if a.sub != "show":
        persist(sess, story, f"estimate:{a.sub}", push=a.sub == "confirm")
    out({"ok": True, "estimate": story.get("estimate")})


def cmd_manual(a):
    """Manual (non-AI) effort for phases the agent does not run: Transition to Live, Support."""
    sid, sess, story = ctx(a)
    if a.phase not in S.MANUAL_STAGES:
        out({"ok": False, "reason": f"phase must be one of {S.MANUAL_STAGES}"}, 2)
    if not a.minutes or a.minutes <= 0:
        out({"ok": False, "reason": "--minutes must be > 0"}, 2)
    end = utcnow()
    if a.date:
        try:
            end = parse_ts(a.date + "T12:00:00Z")
        except ValueError:
            out({"ok": False, "reason": "--date must be YYYY-MM-DD"}, 2)
    start = end.timestamp() - a.minutes * 60
    E.add_entry(story, session_id=sid, stage=a.phase, kind="manual", start=start, end=end,
                note=a.note or f"manual {a.phase} effort (no AI)")
    persist(sess, story, f"manual:{a.phase}", push=True)
    out({"ok": True, "phase": a.phase, "minutes": a.minutes, "note": "Reported as manual effort; no AI claim."})


def cmd_activity(a):
    """Commands with no gate of their own (research, db-analysis, unit-test, security-review, document):
    book their time to the stage they belong to instead of leaving it unassigned."""
    sid, sess, story = ctx(a)
    if a.sub == "start":
        stage = S.ACTIVITY_STAGE.get(a.name)
        if not stage:
            out({"ok": False, "reason": f"unknown activity; one of {sorted(S.ACTIVITY_STAGE)}"}, 2)
        sess["activity"] = {"name": a.name, "stage": stage}
        S.log_stage_event(story, stage, "activity_start")
        persist(sess, story)
        out({"ok": True, "activity": a.name, "booked_to_stage": stage})
    cur = sess.get("activity")
    if cur:
        S.log_stage_event(story, cur["stage"], "activity_end")
    sess["activity"] = None
    persist(sess, story)
    out({"ok": True, "ended": (cur or {}).get("name")})


def cmd_otel(a):
    if a.sub == "check":
        res = otel.check()
        out(res, 0 if res.get("ok") else 3)
    sid, sess, story = ctx(a)
    res = otel.import_into_story(story, force=True)
    persist(sess, story)
    out(res, 0 if res.get("ok") else 3)


def cmd_turn(a):
    sid, sess, story = ctx(a)
    if a.sub == "start":
        r = manual.turn_start(sess, chars=a.chars)
        S.save_session(sess)
        out(r)
    if a.sub == "end":
        r = manual.turn_end(sess, story, sid, actual_credits=a.actual_credits)
        if not r["ok"]:
            S.save_session(sess)
            out(r, 3)
        otel.import_into_story(story)
        persist(sess, story)
        out(r)


def cmd_gate_manual(a):
    """Only meaningful on an UNHOOKED session; see docs/mda/runtimes.md."""
    sid, sess, story = ctx(a)
    fn = manual.gate_approve if a.sub == "approve" else manual.gate_request_changes
    r = fn(sess, story, sid, a.verbatim or "")
    if not r["ok"]:
        S.save_session(sess)
        out(r, 3 if r["reason"] != "verbatim_does_not_match" else 2)
    res = persist(sess, story, f"gate:{r['stage']}:{a.sub}", push=True)
    out({**r, "sync": res})


def cmd_sync(a):
    sid, sess, story = ctx(a, need_story=a.sub != "flush")
    if a.sub == "flush":
        out({"ok": True, "results": sync.flush_all("manual")})
    if a.sub == "push":
        res = persist(sess, story, "manual", push=True)
        out(res, 0 if res and res.get("ok") else 3)
    if a.sub == "check":
        res = sync.check(story, hook=False)
        persist(sess, story)
        out(res, 0 if res.get("ok") else 3)


def cmd_report(a):
    sid, sess, story = ctx(a)
    imp = otel.import_into_story(story)
    if imp.get("usage_entries_changed") or imp.get("turn_time_entries_added"):
        persist(sess, story)
    md = R.markdown(story)
    p = repo_root() / "docs" / "mda" / str(story["story_id"]) / "report.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md, encoding="utf-8")
    (p.with_suffix(".json")).write_text(json.dumps(R.build(story), indent=2, default=str), encoding="utf-8")
    (p.parent / "usage-metrics.ndjson").write_text(metrics.to_ndjson(metrics.build_records(story)), encoding="utf-8")
    res = {"ok": True, "report": str(p.relative_to(repo_root())), "otel_import": imp, "markdown": md if a.print else None}
    if a.wiki:
        try:
            cfg = load_config()
            res["wiki"] = AdoClient(project=story["project"]).wiki_append(cfg["ado"]["wiki_report_path"], md)
        except AdoError as e:
            res["wiki_error"] = str(e)
    out(res)


def cmd_metrics(a):
    sid, sess, story = ctx(a)
    recs = metrics.build_records(story)
    nd = metrics.to_ndjson(recs)
    p = Path(a.out) if a.out else repo_root() / "docs" / "mda" / str(story["story_id"]) / "usage-metrics.ndjson"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(nd, encoding="utf-8")
    out({"ok": True, "records": len(recs), "file": str(p), "schema": metrics.SCHEMA})


def cmd_usage(a):
    sid, sess, story = ctx(a)
    login = story["setup"].get("account", {}).get("confirmed_login")
    if not login:
        out({"ok": False, "reason": "no confirmed account"}, 3)
    try:
        out({"ok": True, **usage.sync(login)})
    except Exception as e:
        out({"ok": False, "reason": str(e)}, 3)


def cmd_sonar(a):
    r = sonar.fetch_pr(a.pr)
    out(r, 0 if r.get("ok") else 3)


def cmd_ado(a):
    sid, sess, story = ctx(a, need_story=False)
    c = AdoClient(project=getattr(a, "project", None) or (story or {}).get("project")
                  or load_config()["ado"]["project"] or "")
    if a.sub == "check":
        res = identity.check_pat(c)
        out(res, 3 if res["status"] == "blocked" else 0)
    if a.sub == "selftest":
        if not c.configured:
            out({"ok": False, "reason": "ado_not_configured",
                 "message": "Set MDA_ADO_PAT, MDA_ADO_ORG_URL and the project (see getting-started.md)."}, 3)
        res = c.selftest()
        out(res, 0 if res.get("ok") else 3)
    if a.sub == "analytics":
        out({"ok": True, "exposed": c.analytics_fields_exposed(),
             "note": "false = field not visible to OData yet; Analytics can lag hours after adding fields."})
    if a.sub == "queries":
        tag = load_config()["ado"]["record_tag"]
        out({"ok": True, "queries": {
            "all_records": f"Select [System.Id],[System.Title] From WorkItems Where [System.Tags] Contains '{tag}'",
            "by_project": f"... And [Custom.MDAProject] = '<project>'",
            "by_sprint": f"... And [Custom.MDASprint] = '<sprint>'"}})


def cmd_doctor(a):
    """One-shot readiness check for this machine/workspace. Nothing is changed (ADO is only probed)."""
    import os
    import sys as _sys
    cfg = load_config()
    checks = []

    def add_(name, status, detail, fix=""):
        checks.append({"check": name, "status": status, "detail": detail, **({"fix": fix} if fix else {})})

    add_("python", "ok" if _sys.version_info >= (3, 9) else "fail", _sys.version.split()[0],
         "Install Python 3.9 or newer")
    pre = identity.prerequisites()
    add_("git", "ok" if pre["git"] else "fail", "found" if pre["git"] else "missing", "Install git")
    add_("gh", "ok" if pre["gh"] else "warn", "found" if pre["gh"] else "missing (needed to confirm the account)",
         "Install GitHub CLI and run `gh auth login`")
    if pre["gh"]:
        add_("gh authenticated", "ok" if pre["gh_authenticated"] else "warn", str(pre["gh_authenticated"]),
             "Run `gh auth login`")
    root = repo_root()
    hooks_ok = (root / ".github/hooks/mda-hooks.json").exists()
    add_("hooks file", "ok" if hooks_ok else "fail", ".github/hooks/mda-hooks.json " + ("present" if hooks_ok else "missing"))
    add_("agents + prompts", "ok" if (root / ".github/agents/migration-delivery.agent.md").exists() and
         (root / ".github/prompts/setup.prompt.md").exists() else "fail",
         "orchestrator and /setup prompt " + ("present" if (root / ".github/agents/migration-delivery.agent.md").exists() else "missing"))
    pat = identity.pat_from_env()
    add_("ADO PAT", "ok" if pat else "fail", "set" if pat else "MDA_ADO_PAT not set",
         "Create a PAT and set MDA_ADO_PAT (getting-started.md step 3)")
    add_("ADO org URL", "ok" if cfg["ado"]["org_url"] else "fail", cfg["ado"]["org_url"] or "not set",
         "Set MDA_ADO_ORG_URL=https://dev.azure.com/<org>")
    projects = known_projects(cfg)
    add_("ADO projects", "ok" if projects else "warn",
         ", ".join(projects) if projects else "no ado.projects configured (any project name is accepted)",
         "List your projects under ado.projects in .mda/config.local.json")
    if pat and cfg["ado"]["org_url"]:
        proj = cfg["ado"]["project"] or (projects[0] if projects else "")
        if proj:
            res = identity.check_pat(AdoClient(project=proj))
            add_(f"ADO PAT + scopes ({proj})", {"ok": "ok", "warn": "warn"}.get(res["status"], "fail"),
                 "; ".join(res.get("messages") or []) or json.dumps(res.get("scopes")),
                 "Regenerate the PAT with Work Items read/write, Wiki read/write, Analytics read")
        else:
            add_("ADO PAT + scopes", "warn", "no project known; set MDA_ADO_PROJECT or ado.projects")
    o = otel.check()
    add_("Copilot OpenTelemetry", "ok" if o.get("ok") else "warn",
         (f"{o.get('chat_with_tokens')} chat spans with tokens in {o.get('file')}" if o.get("ok")
          else o.get("reason") or "; ".join(o.get("warnings") or ["no token data"])),
         "Enable the settings in .github/docs/mda/otel-setup.md, run one chat turn, then re-run")
    add_("Python openpyxl (local Excel preview only)", "ok" if _has("openpyxl") else "warn",
         "installed" if _has("openpyxl") else "not installed (the ADO pipeline installs it itself)",
         "pip install openpyxl")
    fails = [c for c in checks if c["status"] == "fail"]
    out({"ok": not fails, "failed": len(fails), "warnings": sum(1 for c in checks if c["status"] == "warn"),
         "checks": checks, "note": "Also run `mda.py ado selftest` once to prove the work item type and fields."},
        0 if not fails else 3)


def _has(mod: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(mod) is not None


def cmd_session(a):
    sid, sess, story = ctx(a, need_story=False)
    out({"ok": True, "version": __version__, "session_id": sid, "bound_story": sess.get("story_id"),
         "hooked": sess.get("hooked", False),
         "runtime_note": "hooked=false: no Copilot CLI hook has fired yet for this session. If you "
                         "are running via VS Code Copilot Chat (dropdown agent), that is expected - "
                         "self-drive with `turn start`/`turn end` and `gate approve/request-changes "
                         "--verbatim`. See docs/mda/runtimes.md." if not sess.get("hooked") else
                         "hooked=true: the hook layer is active and already drives timing/gates; "
                         "do not call turn/gate-approve yourself.",
         "warnings": sess.get("warnings", []), "local_stories": S.list_local_stories(),
         "active_stage": sess.get("active_stage"), "escalated": sess.get("escalated")})


def build_parser():
    p = argparse.ArgumentParser(prog="mda")
    p.add_argument("--session-id")
    sp = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, subs=None):
        q = sp.add_parser(name)
        q.set_defaults(func=fn)
        if subs:
            q.add_argument("sub", choices=subs)
        return q

    add("session", cmd_session)
    q = add("setup", cmd_setup, ["status", "prereqs", "pat", "accounts", "set", "confirm-account", "otel"])
    q.add_argument("--application"); q.add_argument("--tech-stack")
    q.add_argument("--project"); q.add_argument("--story-id"); q.add_argument("--migration", choices=["yes", "no"])
    for k in ("old", "new", "hld", "hlsa", "lld"):
        q.add_argument(f"--{k}")
    q.add_argument("--login"); q.add_argument("--force-unlisted", action="store_true")
    q.add_argument("--auto-continue", choices=["yes", "no"])
    q = add("story", cmd_story, ["list", "resume", "recover", "status", "ado-summary", "pr-raised", "complete", "reopen"])
    q.add_argument("--id"); q.add_argument("--project"); q.add_argument("--url"); q.add_argument("--number", type=int)
    q.add_argument("--answer", choices=["yes", "no"]); q.add_argument("--trigger"); q.add_argument("--reason")
    q = add("stage", cmd_stage, ["start", "wait-input", "resume"])
    q.add_argument("--stage"); q.add_argument("--trigger")
    q = add("gate", cmd_gate, ["status", "submit"])
    q.add_argument("--stage"); q.add_argument("--summary"); q.add_argument("--no-artifact", action="store_true")
    q = add("complexity", cmd_complexity, ["counts", "score", "adjust", "confirm", "calibrate"])
    q.add_argument("--json"); q.add_argument("--tier"); q.add_argument("--note", default="")
    q.add_argument("--history"); q.add_argument("--accept", action="store_true")
    q = add("qa", cmd_qa, ["log-execution", "outcome"])
    q.add_argument("--minutes", type=float); q.add_argument("--note"); q.add_argument("--result", choices=["pass", "reopen"])
    q.add_argument("--reason")
    q = add("benefits", cmd_benefits); q.add_argument("--project", required=True); q.add_argument("--print", action="store_true")
    q.add_argument("--from", dest="date_from"); q.add_argument("--to", dest="date_to"); q.add_argument("--xlsx", action="store_true")
    q = add("estimate", cmd_estimate, ["show", "set", "confirm"])
    q.add_argument("--phase", choices=list(EST.PHASES)); q.add_argument("--pd", type=float)
    q.add_argument("--reason"); q.add_argument("--json"); q.add_argument("--source", choices=["developer", "llm"], default="developer")
    q = add("manual", cmd_manual, ["log"])
    q.add_argument("--phase"); q.add_argument("--minutes", type=float); q.add_argument("--note"); q.add_argument("--date")
    q = add("activity", cmd_activity, ["start", "end"])
    q.add_argument("--name")
    add("otel", cmd_otel, ["check", "import"])
    q = add("turn", cmd_turn, ["start", "end"])
    q.add_argument("--chars", type=int); q.add_argument("--actual-credits", type=float)
    q = add("gate-manual", cmd_gate_manual, ["approve", "request-changes"])
    q.add_argument("--verbatim")
    add("sync", cmd_sync, ["push", "check", "flush"])
    q = add("report", cmd_report); q.add_argument("--wiki", action="store_true"); q.add_argument("--print", action="store_true")
    q = add("metrics", cmd_metrics); q.add_argument("--out")
    add("usage", cmd_usage)
    q = add("sonar", cmd_sonar); q.add_argument("--pr", type=int, required=True)
    q = add("ado", cmd_ado, ["check", "analytics", "queries", "selftest"])
    q.add_argument("--project")
    add("doctor", cmd_doctor)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # surface a clean JSON error rather than a traceback
        out({"ok": False, "reason": f"{type(exc).__name__}: {exc}"}, 1)
