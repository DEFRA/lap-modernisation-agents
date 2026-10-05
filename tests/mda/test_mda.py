"""Run: python -m unittest discover -s tests/mda -v   (stdlib only, no network)."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / ".github" / "lib"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / ".github/config").parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO / ".github/config", self.tmp / ".github/config")
        os.environ["MDA_ROOT"] = str(self.tmp)
        for k in ("MDA_ADO_PAT", "MDA_ADO_ORG_URL", "MDA_ADO_PROJECT"):
            os.environ.pop(k, None)
        from mda import state
        self.S = state
        self.story = state.new_story("Proj", 1234)
        self.story["setup"].update({"is_migration": False, "account": {"confirmed_login": "dev1"}})

    def tearDown(self):
        os.environ.pop("MDA_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def art(self, stage):
        p = self.S.artifact_path(self.story["story_id"], stage)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")


class TestState(Base):
    def test_setup_blocks_until_complete(self):
        s = self.S.new_story("P", 1)
        self.assertTrue(self.S.setup_missing(s))
        r = self.S.start_stage(s, "requirements")
        self.assertEqual(r["reason"], "setup_incomplete")

    def test_migration_requires_paths(self):
        s = self.S.new_story("P", 1)
        s["setup"].update({"is_migration": True, "account": {"confirmed_login": "a"}})
        miss = self.S.setup_missing(s)
        self.assertEqual(len(miss), 5)

    def test_prereq_enforced_and_gate_flow(self):
        s = self.story
        self.assertEqual(self.S.start_stage(s, "discovery")["reason"], "prerequisite_not_approved")
        self.assertTrue(self.S.start_stage(s, "requirements")["ok"])
        self.assertEqual(self.S.submit_stage(s, "requirements", "x")["reason"], "artifact_missing")
        self.art("requirements")
        self.assertTrue(self.S.submit_stage(s, "requirements", "x")["ok"])
        self.assertEqual(self.S.start_stage(s, "requirements")["reason"], "awaiting_approval")
        self.S.request_changes(s, "requirements", "more")
        self.assertEqual(s["stages"]["requirements"]["status"], "in_progress")
        self.S.submit_stage(s, "requirements", "x")
        self.S.approve_stage(s, "requirements")
        self.assertTrue(self.S.start_stage(s, "discovery")["ok"])

    def _to_pr_approved(self):
        for st in ("requirements", "discovery", "plan", "build", "quality", "pr"):
            self.S.start_stage(self.story, st)
            self.story["stages"][st]["status"] = "approved"

    def test_cycles_only_bump_after_complete(self):
        s = self.story
        self._to_pr_approved()
        r = self.S.reopen(s, "pr-review")
        self.assertFalse(r["cycle_incremented"])
        self.assertEqual(s["cycle"], 1)
        self.S.mark_complete(s, True)
        r = self.S.reopen(s, "sonar-recheck")
        self.assertTrue(r["cycle_incremented"])
        self.assertEqual(s["cycle"], 2)
        self.assertEqual(len(s["cycle_history"]), 1)
        self.assertEqual(s["stages"]["build"]["status"], "not_started")
        self.assertEqual(s["stages"]["pr"]["status"], "approved")

    def test_qa_reopen_is_next_cycle_tagged(self):
        s = self.story
        self._to_pr_approved()
        self.S.mark_complete(s, True)
        r = self.S.qa_outcome(s, "reopen", "bug")
        self.assertEqual((r["cycle"], r["trigger"]), (2, "qa-defect"))
        self.assertEqual(s["reopen_log"][-1]["trigger"], "qa-defect")


class TestAutoContinue(Base):
    def test_chain_and_stop_at_pr(self):
        s = self.story
        self.assertFalse(s["setup"]["auto_continue"])
        self.assertEqual(self.S.next_auto_stage(s), "requirements")
        for st in ("requirements", "discovery", "plan", "build", "quality"):
            s["stages"][st]["status"] = "approved"
        self.assertEqual(self.S.next_auto_stage(s), "pr")
        s["stages"]["pr"]["status"] = "approved"
        self.assertIsNone(self.S.next_auto_stage(s))  # QA / fixes are never auto-started

    def test_hook_context_follows_setting(self):
        from mda import hooks
        S = self.S
        for flag in (True, False):
            self.story["setup"]["auto_continue"] = flag
            self.story["stages"]["requirements"]["status"] = "awaiting_approval"
            S.save_story(self.story)
            sess = S.load_session("ac")
            sess["story_id"] = "1234"
            S.save_session(sess)
            out = hooks.dispatch("userPromptSubmitted", {"sessionId": "ac", "prompt": "approve"})
            self.assertIn("Auto-continue is ON" if flag else "Auto-continue is OFF", out["additionalContext"])


class TestEffort(Base):
    def test_only_bounded_intervals_summed(self):
        from mda import effort as E
        s = self.story
        t0 = 1_700_000_000
        E.add_entry(s, session_id="a", stage="build", kind="ai", start=t0, end=t0 + 100)
        E.add_entry(s, session_id="a", stage="build", kind="approval", start=t0 + 100, end=t0 + 160)
        # a night later: second session, must not add the overnight gap
        E.add_entry(s, session_id="b", stage="build", kind="ai", start=t0 + 86400, end=t0 + 86400 + 50)
        E.add_entry(s, session_id="a", stage="build", kind="subagent", start=t0, end=t0 + 90, agent="x")
        tot = E.story_totals(s)
        self.assertEqual(tot["active_seconds_total"], 210)  # subagent not double counted
        self.assertGreater(tot["calendar_seconds"], 86000)  # calendar reported separately

    def test_idle_approval_gap_is_excluded_not_capped(self):
        from mda import effort as E
        e = E.add_entry(self.story, session_id="a", stage="build", kind="approval", start=0, end=10 * 3600)
        self.assertTrue(e["capped"] and e["idle_excluded"])
        self.assertEqual(e["seconds"], 0)  # developer was away: no invented 2 hours

    def test_overlong_ai_turn_is_capped(self):
        from mda import effort as E
        e = E.add_entry(self.story, session_id="a", stage="build", kind="ai", start=0, end=10 * 3600)
        self.assertTrue(e["capped"])
        self.assertEqual(e["seconds"], 120 * 60)

    def test_qa_execution_separate_phase(self):
        from mda import effort as E
        E.add_entry(self.story, session_id="a", stage="qa_execution", kind="manual", start=0, end=1800)
        E.add_entry(self.story, session_id="a", stage="build", kind="ai", start=0, end=600)
        p = E.story_totals(self.story)["active_seconds_by_phase"]
        self.assertEqual((p["qa-execution"], p["dev"]), (1800, 600))

    def test_sprint_split_across_boundary(self):
        from mda import effort as E
        from mda.core import load_config
        cfg = load_config()
        cfg["effort"]["timezone"] = "UTC"
        cfg["sprints"] = [{"name": "S1", "start": "2026-01-01", "end": "2026-01-01"},
                          {"name": "S2", "start": "2026-01-02", "end": "2026-01-14"}]
        a = dt.datetime(2026, 1, 1, 23, 0, tzinfo=dt.timezone.utc)
        E.add_entry(self.story, session_id="a", stage="build", kind="ai", start=a,
                    end=a + dt.timedelta(hours=2), cfg=cfg)
        b = E.by_sprint(self.story, cfg)
        self.assertAlmostEqual(b["S1"]["dev"], 3600, delta=1)
        self.assertAlmostEqual(b["S2"]["dev"], 3600, delta=1)


class TestComplexity(Base):
    def test_score_and_raw_data_kept(self):
        from mda import complexity as C
        r = C.score({"screen_simple": 4, "complex_form": 2, "external_integration": 1})
        self.assertEqual(r["score"], 13)  # 4 + 6 + 3
        self.assertEqual(r["tier"], "Medium")
        self.assertEqual(r["counts"]["complex_form"], 2)
        self.assertEqual(r["weights"]["complex_form"], 3)
        self.assertIsNotNone(r["warning"])  # uncalibrated banner

    def test_bands(self):
        from mda import complexity as C
        self.assertEqual(C.score({"screen_simple": 10})["tier"], "Low")
        self.assertEqual(C.score({"screen_simple": 51})["tier"], "Very High")

    def test_rejects_unknown_factor(self):
        from mda import complexity as C
        with self.assertRaises(ValueError):
            C.score({"bogus": 1})

    def test_calibrate_needs_min_rows_and_fits(self):
        from mda import complexity as C
        import csv
        p = self.tmp / "h.csv"
        factors = list(C.load_model()["weights"])
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["story_id", "actual_traditional_days"] + factors)
            for i in range(12):
                row = [i + 1, 0] + [(i * (j + 2)) % 5 for j in range(len(factors))]
                row[1] = round(0.3 * row[2] + 0.9 * row[3] + 0.4 * row[8] + 1, 2)
                w.writerow(row)
        res = C.calibrate(str(p))
        self.assertGreater(res["fit"]["r_squared"], 0.9)
        self.assertFalse(res["proposed_model"]["calibrated"])
        with open(p, "w", newline="") as f:
            f.write("story_id,actual_traditional_days\n1,2\n")
        with self.assertRaises(ValueError):
            C.calibrate(str(p))


class TestGate(Base):
    def test_classify(self):
        from mda import gate
        self.assertEqual(gate.classify_prompt("/approve looks good"), ("approve", "looks good"))
        self.assertEqual(gate.classify_prompt("Approved")[0], "approve")
        self.assertEqual(gate.classify_prompt("request changes: rename x"), ("changes", "rename x"))
        self.assertEqual(gate.classify_prompt("please approve of nothing")[0], None)

    def test_tool_gating(self):
        from mda import gate
        kw = dict(setup_missing=[], awaiting=None, escalated=False, bound=True)
        self.assertTrue(gate.tool_decision("edit", {}, **kw)["allow"])
        self.assertFalse(gate.tool_decision("edit", {}, **{**kw, "awaiting": "plan"})["allow"])
        self.assertTrue(gate.tool_decision("view", {}, **{**kw, "awaiting": "plan"})["allow"])
        self.assertTrue(gate.tool_decision("bash", {"command": "python .github/scripts/mda.py gate status"},
                                           **{**kw, "awaiting": "plan"})["allow"])
        self.assertFalse(gate.tool_decision("bash", {"command": "dotnet build"}, **{**kw, "setup_missing": ["x"]})["allow"])
        self.assertFalse(gate.tool_decision("edit", {}, **{**kw, "escalated": True})["allow"])
        self.assertTrue(gate.tool_decision("edit", {}, **{**kw, "bound": False})["allow"])


class FakeTransport:
    """In-memory ADO: work items keyed by title."""
    def __init__(self):
        self.items, self.next = {}, 1
        self.calls = []
        self.reject_custom = False
        self.reject_links = False

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url))
        data = json.loads(body) if body else None
        if "wit/wiql" in url:
            q = data["query"]
            titles = {i: it["fields"].get("System.Title", "") for i, it in self.items.items()}
            if "[System.Title] = '" in q:
                want = q.split("[System.Title] = '")[1].split("'")[0]
                ids = [i for i, t in titles.items() if t == want]
            elif "[System.Title] Contains '" in q:
                frag = q.split("[System.Title] Contains '")[1].split("'")[0]
                ids = [i for i, t in titles.items() if frag in t]
            else:
                ids = list(titles)
            return 200, {}, json.dumps({"workItems": [{"id": i} for i in ids]}).encode()
        if "wit/workitems/" in url and method == "DELETE":
            self.items.pop(int(url.split("workitems/")[1].split("?")[0]), None)
            return 200, {}, b"{}"
        if "wit/workitems" in url and method in ("POST", "PATCH"):
            if self.reject_links and any(op["path"] == "/relations/-" for op in data):
                return 400, {}, b"TF201036: You cannot add a Child link between work items"
            fields = {op["path"].split("/fields/")[1]: op["value"] for op in data if op["path"].startswith("/fields/")}
            if self.reject_custom and any(k.startswith("Custom.") for k in fields):
                return 400, {}, b"TF51535: Cannot find field Custom.MDAProject"
            if method == "POST":
                wid = self.next
                self.next += 1
                self.items[wid] = {"id": wid, "fields": fields}
            else:
                wid = int(url.split("workitems/")[1].split("?")[0])
                self.items[wid]["fields"].update(fields)
            return 200, {}, json.dumps({"id": wid}).encode()
        if "wit/workitems?" in url and "ids=" in url and method == "GET":
            ids = [int(x) for x in url.split("ids=")[1].split("&")[0].replace("%2C", ",").split(",")]
            return 200, {}, json.dumps({"value": [self.items[i] for i in ids]}).encode()
        if "wit/workitems/" in url and method == "GET":
            wid = int(url.split("workitems/")[1].split("?")[0])
            return 200, {}, json.dumps(self.items[wid]).encode()
        return 404, {}, b"nope"


class TestSync(Base):
    def client(self, ft):
        os.environ["MDA_ADO_ORG_URL"] = "https://dev.azure.com/org"
        from mda.ado import AdoClient
        return AdoClient(project="Proj", pat="x", transport=ft)

    def test_push_recover_roundtrip_and_rows(self):
        from mda import effort as E, sync
        ft = FakeTransport()
        c = self.client(ft)
        s = self.story
        E.add_entry(s, session_id="a", stage="build", kind="ai", start=1_700_000_000, end=1_700_000_600)
        E.add_entry(s, session_id="a", stage="build", kind="usage", start=1_700_000_000, end=1_700_000_500,
                    agent="build-engineer", model="gpt-x", tokens_in=1000, tokens_out=200, token_source="otel")
        s["complexity"]["result"] = __import__("mda.complexity", fromlist=["x"]).score({"screen_simple": 3})
        s["estimate"] = __import__("mda.estimate", fromlist=["x"]).set_many(
            None, {"build": {"pd": 3, "reason": "three simple screens"}})
        r = sync.push(s, "gate", client=c)
        self.assertTrue(r["ok"], r)
        titles = {i["fields"]["System.Title"]: i["fields"] for i in ft.items.values()}
        self.assertIn("MDA-1234-state-dev1", titles)
        self.assertIn("MDA-1234-estimate", titles)
        row_title = next(t for t in titles if t.startswith("MDA-1234-dev1-") and t.endswith("-c1-build"))
        f = titles[row_title]
        self.assertEqual(f["Custom.MDADeveloper"], "dev1")
        self.assertEqual(f["Custom.MDATokensIn"], 1000)       # real tokens, kept apart from the estimate
        self.assertEqual(f["Custom.MDATokenSource"], "otel")
        self.assertAlmostEqual(f["Custom.MDAAiHours"], 600 / 3600, places=3)
        self.assertIn("Custom.MDAWorkDate", f)
        self.assertEqual(titles["MDA-1234-estimate"]["Custom.MDATier"], "Low")
        # unchanged rows are not rewritten
        n = len(ft.calls)
        sync.push(s, "again", client=c)
        self.assertLess(len(ft.calls) - n, n)
        remote, why = sync.recover("1234", client=c)
        self.assertEqual(why, "recovered")
        self.assertEqual(len(remote["effort"]), 2)

    def test_two_developers_never_overwrite_each_other(self):
        from mda import effort as E, sync
        ft = FakeTransport()
        c = self.client(ft)
        a = self.story
        b = json.loads(json.dumps(self.story))
        b["setup"]["account"] = {"confirmed_login": "dev2"}
        E.add_entry(a, session_id="a", stage="build", kind="ai", start=1_700_000_000, end=1_700_000_600)
        E.add_entry(b, session_id="b", stage="build", kind="ai", start=1_700_000_000, end=1_700_001_200)
        self.assertTrue(sync.push(a, "x", client=c)["ok"])
        self.assertTrue(sync.push(b, "x", client=c)["ok"])
        titles = [i["fields"]["System.Title"] for i in ft.items.values()]
        self.assertEqual(len([t for t in titles if t.endswith("-c1-build")]), 2)      # one row each
        self.assertEqual(len([t for t in titles if "-state-" in t]), 2)               # one snapshot each
        merged, why = sync.recover("1234", client=c)
        self.assertEqual(len(merged["effort"]), 2)                                    # nothing lost
        # a's next drift check pulls b's work in, and keeps a's own identity
        res = sync.check(a, client=c)
        self.assertEqual(res["pulled_entries"], 1)
        self.assertEqual(a["setup"]["account"]["confirmed_login"], "dev1")
        self.assertEqual(len(a["effort"]), 2)

    def test_project_override_for_two_teams(self):
        from mda.ado import AdoClient, known_projects
        from mda.core import load_config
        cfg = load_config()
        cfg["ado"]["org_url"] = "https://dev.azure.com/main"
        cfg["ado"]["projects"] = [{"name": "TeamB", "org_url": "https://dev.azure.com/other/", "wiki_id": "wb"}]
        c = AdoClient(cfg=cfg, project="teamb", pat="x")
        self.assertEqual((c.org, c.wiki_id), ("https://dev.azure.com/other", "wb"))
        self.assertEqual(known_projects(cfg), ["TeamB"])
        self.assertEqual(AdoClient(cfg=cfg, project="TeamA", pat="x").org, "https://dev.azure.com/main")

    def test_payload_only_fallback(self):
        from mda import sync
        ft = FakeTransport()
        ft.reject_custom = True
        r = sync.push(self.story, "x", client=self.client(ft))
        self.assertTrue(r["ok"], r)
        self.assertTrue(all("Custom.MDAProject" not in i["fields"] for i in ft.items.values()))
        self.assertTrue(all("System.Description" in i["fields"] for i in ft.items.values()))

    def test_offline_marks_dirty_never_raises(self):
        from mda import sync
        from mda.ado import AdoClient
        c = AdoClient(project="Proj", pat=None)
        r = sync.push(self.story, "x", client=c)
        self.assertFalse(r["ok"])

    def test_drift_detection(self):
        from mda import sync
        ft = FakeTransport()
        c = self.client(ft)
        sync.push(self.story, "x", client=c)
        other = json.loads(json.dumps(self.story))
        other["project"] = "OtherProject"
        self.assertEqual(sync.check(other, client=c)["reason"], "drift_mismatch")

    def test_merge_keeps_local_entries(self):
        from mda import effort as E, sync
        local = self.story
        remote = json.loads(json.dumps(local))
        remote["sync"]["revision"] = 5
        E.add_entry(remote, session_id="r", stage="plan", kind="ai", start=0, end=10)
        E.add_entry(local, session_id="l", stage="build", kind="ai", start=0, end=10)
        merged = sync.merge_remote(local, remote)
        self.assertEqual(len(merged["effort"]), 2)


class TestHooksEndToEnd(Base):
    def run_hook(self, event, payload):
        from mda import hooks
        payload.setdefault("sessionId", "sess1")
        os.environ["MDA_DEBUG"] = "1"
        return hooks.dispatch(event, payload)

    def test_full_gate_cycle_with_effort(self):
        S = self.S
        S.save_story(self.story)
        sess = S.load_session("sess1")
        sess["story_id"] = "1234"
        S.save_session(sess)
        t = 1_800_000_000_000
        self.run_hook("sessionStart", {"timestamp": t})
        # start a stage
        s, _ = S.load_story("1234")
        S.start_stage(s, "requirements")
        S.save_story(s)
        sess = S.load_session("sess1")
        sess.update({"active_stage": "requirements", "stage_run_open": True})
        S.save_session(sess)
        # prompt + agent stop without submission -> blocked, forced continuation
        self.run_hook("userPromptSubmitted", {"timestamp": t, "prompt": "do requirements"})
        out = self.run_hook("agentStop", {"timestamp": t + 30_000})
        self.assertEqual(out.get("decision"), "block")
        # agent submits
        self.art("requirements")
        s, _ = S.load_story("1234")
        S.submit_stage(s, "requirements", "done")
        S.save_story(s)
        sess = S.load_session("sess1")
        sess["stage_run_open"] = False
        S.save_session(sess)
        # tools denied while awaiting approval
        d = self.run_hook("preToolUse", {"toolName": "edit", "toolArgs": {}})
        self.assertEqual(d.get("permissionDecision"), "deny")
        # a non-approval chat message leaves state alone
        self.run_hook("userPromptSubmitted", {"timestamp": t + 40_000, "prompt": "why did you do that?"})
        self.run_hook("agentStop", {"timestamp": t + 50_000})
        s, _ = S.load_story("1234")
        self.assertEqual(s["stages"]["requirements"]["status"], "awaiting_approval")
        # human approves 10 min after the last agent response
        self.run_hook("userPromptSubmitted", {"timestamp": t + 50_000 + 600_000, "prompt": "/approve"})
        s, _ = S.load_story("1234")
        self.assertEqual(s["stages"]["requirements"]["status"], "approved")
        kinds = {}
        from mda import effort as E
        for x in s["effort"]:
            kinds[x["kind"]] = kinds.get(x["kind"], 0) + x["seconds"]
        self.assertEqual(kinds["ai"], 40)          # 30s + 10s of AI processing
        self.assertEqual(kinds["approval"], 600)   # approval - last agent response
        d = self.run_hook("preToolUse", {"toolName": "edit", "toolArgs": {}})
        self.assertEqual(d, {})

    def test_self_heal_escalation(self):
        S = self.S
        S.save_story(self.story)
        sess = S.load_session("sess1")
        sess["story_id"] = "1234"
        S.save_session(sess)
        for _ in range(3):
            out = self.run_hook("postToolUseFailure", {})
        self.assertIn("additionalContext", out)
        d = self.run_hook("permissionRequest", {"toolName": "bash", "toolArgs": {"command": "dotnet test"}})
        self.assertEqual(d.get("behavior"), "deny")
        self.run_hook("userPromptSubmitted", {"prompt": "carry on"})  # human input clears escalation
        d = self.run_hook("permissionRequest", {"toolName": "bash", "toolArgs": {"command": "dotnet test"}})
        self.assertEqual(d, {})

    def test_hook_never_raises_on_garbage(self):
        os.environ.pop("MDA_DEBUG", None)
        from mda import hooks
        self.assertEqual(hooks.dispatch("agentStop", {"sessionId": "zz"}), {})
        self.assertEqual(hooks.dispatch("unknownEvent", {}), {})


class TestManualRuntime(Base):
    def test_hooked_session_ignores_manual_calls(self):
        from mda import manual
        sess = self.S.load_session("x"); sess["hooked"] = True
        self.assertEqual(manual.turn_start(sess), {"ok": True, "skipped": "hooked_session"})
        r = manual.gate_approve(sess, self.story, "x", "approve")
        self.assertEqual(r, {"ok": False, "reason": "hooked_session",
                             "message": r["message"]})

    def test_turn_start_end_records_ai_effort(self):
        from mda import manual
        sess = self.S.load_session("x")
        manual.turn_start(sess)
        r = manual.turn_end(sess, self.story, "x")
        self.assertTrue(r["ok"])
        self.assertEqual(self.story["effort"][-1]["kind"], "ai")
        self.assertIsNone(sess["prompt_start"])

    def test_turn_start_end_estimates_tokens_from_chars(self):
        from mda import manual
        sess = self.S.load_session("x")
        manual.turn_start(sess, chars=400)
        r = manual.turn_end(sess, self.story, "x")
        self.assertTrue(r["ok"])
        self.assertEqual(self.story["effort"][-1]["est_tokens"], 100)
        self.assertIsNone(self.story["effort"][-1]["actual_credits"])

    def test_turn_end_records_developer_attested_actual_credits(self):
        from mda import manual
        sess = self.S.load_session("x")
        manual.turn_start(sess, chars=400)
        r = manual.turn_end(sess, self.story, "x", actual_credits=24.3)
        self.assertTrue(r["ok"])
        self.assertEqual(r["actual_credits"], 24.3)
        self.assertEqual(self.story["effort"][-1]["actual_credits"], 24.3)

    def test_turn_end_without_start_is_rejected(self):
        from mda import manual
        sess = self.S.load_session("x")
        r = manual.turn_end(sess, self.story, "x")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "no_open_turn")

    def test_gate_approve_rejects_non_verbatim_and_accepts_real(self):
        from mda import manual
        s = self.story
        self.art("requirements")
        self.S.start_stage(s, "requirements")
        self.S.submit_stage(s, "requirements", "x")
        sess = self.S.load_session("x")
        bad = manual.gate_approve(sess, s, "x", "sure, looks fine")
        self.assertEqual(bad["reason"], "verbatim_does_not_match")
        self.assertEqual(s["stages"]["requirements"]["status"], "awaiting_approval")
        good = manual.gate_approve(sess, s, "x", "approve")
        self.assertTrue(good["ok"])
        self.assertEqual(s["stages"]["requirements"]["status"], "approved")
        self.assertEqual(s["effort"][-1]["kind"], "approval")

    def test_gate_request_changes_reopens_stage(self):
        from mda import manual
        s = self.story
        self.art("requirements")
        self.S.start_stage(s, "requirements")
        self.S.submit_stage(s, "requirements", "x")
        sess = self.S.load_session("x")
        r = manual.gate_request_changes(sess, s, "x", "request changes: fix scope")
        self.assertTrue(r["ok"])
        self.assertEqual(s["stages"]["requirements"]["status"], "in_progress")
        self.assertTrue(sess["stage_run_open"])

    def test_gate_action_needs_awaiting_stage(self):
        from mda import manual
        sess = self.S.load_session("x")
        r = manual.gate_approve(sess, self.story, "x", "approve")
        self.assertEqual(r["reason"], "no_stage_awaiting_approval")


class TestCorruptionRecovery(Base):
    def test_checksum_detects_corruption(self):
        from mda.core import read_json
        self.S.save_story(self.story)
        p = self.tmp / ".mda/stories/story-1234.json"
        obj = json.loads(p.read_text())
        obj["project"] = "Tampered"
        p.write_text(json.dumps(obj))
        self.assertEqual(read_json(p)[1], "corrupt")


class TestSonar(Base):
    def test_annotation_fallback_when_empty_but_failing(self):
        from mda import sonar
        cfg = __import__("mda.core", fromlist=["x"]).load_config()
        cfg["sonar"].update({"organization": "o", "project_key": "k"})

        def get(url, timeout=15):
            if "project_status" in url:
                return 200, {"projectStatus": {"status": "ERROR", "conditions": [{"status": "ERROR", "metricKey": "new_violations"}]}}
            if "issues/search" in url:
                return 200, {"issues": []}
            return 200, {"component": {"measures": []}}
        r = sonar.fetch_pr(7, cfg, get=get, annotations=lambda pr: [{"path": "a.cs", "message": "m"}])
        self.assertTrue(r["used_annotation_fallback"])
        self.assertEqual(len(r["issues"]), 1)


class TestReport(Base):
    def test_report_flags_uncalibrated_and_separates_qa_execution(self):
        from mda import complexity as C, effort as E, report
        s = self.story
        s["complexity"]["result"] = C.score({"screen_simple": 5})
        E.add_entry(s, session_id="a", stage="build", kind="ai", start=0, end=3600)
        E.add_entry(s, session_id="a", stage="qa_execution", kind="manual", start=0, end=1800)
        md = report.markdown(s)
        self.assertIn("UNCALIBRATED", md)
        self.assertIn("QA manual execution (no AI", md)
        self.assertIn("Calendar duration", md)


class TestMetrics(Base):
    def test_github_user_level_shape(self):
        from mda import complexity as C, effort as E, metrics
        s = self.story
        s["complexity"]["result"] = C.score({"screen_simple": 3})
        t = 1_700_000_000
        E.add_entry(s, session_id="a", stage="build", kind="ai", start=t, end=t + 60, est_tokens=100, slash_cmd="/build")
        E.add_entry(s, session_id="b", stage="build", kind="ai", start=t + 90, end=t + 120, est_tokens=50)
        E.add_entry(s, session_id="a", stage="build", kind="subagent", start=t, end=t + 50, agent="build-engineer")
        recs = metrics.build_records(s)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["user_login"], "dev1")
        self.assertEqual(r["user_initiated_interaction_count"], 2)
        self.assertEqual(r["totals_by_cli"]["session_count"], 2)
        self.assertEqual(r["totals_by_cli"]["token_usage"]["prompt_tokens_sum"], 150)
        self.assertIsNone(r["totals_by_cli"]["token_usage"]["output_tokens_sum"])  # unknown, not faked
        self.assertEqual(r["totals_by_slash_cmd"], [{"slash_cmd": "/build", "interaction_count": 1}])
        self.assertEqual(r["totals_by_custom_agent"][0]["custom_agent"], "build-engineer")
        self.assertEqual(r["mda"]["complexity"]["counts"]["screen_simple"], 3)
        self.assertTrue(r["mda"]["tokens_estimated"])
        self.assertEqual(len(metrics.to_ndjson(recs).strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
