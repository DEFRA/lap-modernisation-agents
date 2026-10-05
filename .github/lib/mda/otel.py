"""Real token usage from Copilot's OpenTelemetry file export (VS Code Copilot Chat and Copilot CLI).

Copilot emits, per LLM call (`chat` span) and per agent run (`invoke_agent` span):
gen_ai.usage.input_tokens / output_tokens, model, start/end, gen_ai.conversation.id and
gen_ai.agent.name (sub-agents are nested invoke_agent spans). Reference:
https://github.com/microsoft/vscode-copilot-chat/blob/main/docs/monitoring/agent_monitoring.md

Enable it with a JSON-lines file exporter (docs/mda/otel-setup.md). Content capture stays OFF, so no
prompt or code text is ever in the file.

WHAT IS AND IS NOT VERIFIED: the span attribute names come from the documentation above. The exact
JSON-lines *line format* the file exporter writes has not been observed in this repo, so the reader is
deliberately tolerant (OTLP-JSON `resourceSpans`, OTel-JS console-style spans, flat dicts) and
`mda.py otel check` reports what a real file contains. Run it before trusting any number.

Attribution: OTel knows nothing about stories or stages. Each LLM call is booked to the stage window
that was open when it started (state.stage_at), else to `unassigned`. To keep the story record small,
chat spans are rolled up to one `usage` entry per (user turn, agent, model).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from . import effort as E
from .core import iso, load_config, parse_ts, repo_root
from .state import stage_at

IN_KEY, OUT_KEY = "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"


def otel_path(cfg=None) -> Path:
    cfg = cfg or load_config()
    p = Path(cfg["otel"]["file"])
    return p if p.is_absolute() else repo_root() / p


# ---------------------------------------------------------------- tolerant span reader

def _ts(v):
    """Epoch s/ms/us/ns number or numeric string, OTel hrtime [sec, nanos], or ISO string -> aware UTC datetime."""
    if v is None or v == "":
        return None
    try:
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return dt.datetime.fromtimestamp(float(v[0]) + float(v[1]) / 1e9, dt.timezone.utc)
        if isinstance(v, str) and not v.replace(".", "", 1).isdigit():
            return parse_ts(v)
        n = float(v)
        for floor, scale in ((1e17, 1e9), (1e14, 1e6), (1e11, 1e3)):  # ns, us, ms
            if n > floor:
                return dt.datetime.fromtimestamp(n / scale, dt.timezone.utc)
        return dt.datetime.fromtimestamp(n, dt.timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def _attr_value(v):
    if isinstance(v, dict):
        for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if k in v:
                return v[k]
        return None
    return v


def _attrs(raw) -> dict:
    if isinstance(raw, dict):
        return {k: _attr_value(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {a.get("key"): _attr_value(a.get("value")) for a in raw if isinstance(a, dict)}
    return {}


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _span(obj: dict, service=None):
    """One normalized span from an OTLP-JSON span or a console/flat span dict, else None."""
    a = _attrs(obj.get("attributes"))
    op = a.get("gen_ai.operation.name")
    name = obj.get("name") or ""
    if not op:
        op = "chat" if name.startswith("chat ") else "invoke_agent" if name.startswith("invoke_agent") else None
    if op not in ("chat", "invoke_agent"):
        return None
    ctx = obj.get("spanContext") or {}
    pctx = obj.get("parentSpanContext") or {}
    start = _ts(obj.get("startTimeUnixNano") or obj.get("startTime") or obj.get("start_time"))
    end = _ts(obj.get("endTimeUnixNano") or obj.get("endTime") or obj.get("end_time"))
    if start is None and obj.get("timestamp") is not None:
        start = _ts(obj["timestamp"])
    if end is None and start is not None and obj.get("duration") is not None:
        d = obj["duration"]
        secs = (float(d[0]) + float(d[1]) / 1e9) if isinstance(d, (list, tuple)) else float(d) / 1e6
        end = start + dt.timedelta(seconds=secs)
    if start is None:
        return None
    res = _attrs((obj.get("resource") or {}).get("attributes"))
    return {"trace": obj.get("traceId") or obj.get("trace_id") or ctx.get("traceId"),
            "span": obj.get("spanId") or obj.get("span_id") or obj.get("id") or ctx.get("spanId"),
            "parent": (obj.get("parentSpanId") or obj.get("parentId") or obj.get("parent_id")
                       or pctx.get("spanId") or None),
            "op": op, "name": name, "start": start, "end": end or start,
            "agent": a.get("gen_ai.agent.name"),
            "model": a.get("gen_ai.response.model") or a.get("gen_ai.request.model"),
            "conv": a.get("gen_ai.conversation.id"),
            "tin": _int(a.get(IN_KEY)), "tout": _int(a.get(OUT_KEY)),
            "service": service or res.get("service.name"), "attr_keys": sorted(k for k in a if k)}


def _walk(obj, out):
    """Find spans anywhere in one JSON line (OTLP resourceSpans, wrapped records, plain span)."""
    if not isinstance(obj, dict):
        return
    if "resourceSpans" in obj:
        for rs in obj["resourceSpans"]:
            svc = _attrs((rs.get("resource") or {}).get("attributes")).get("service.name")
            for ss in rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans") or []:
                for sp in ss.get("spans", []):
                    s = _span(sp, svc)
                    if s:
                        out.append(s)
        return
    s = _span(obj)
    if s:
        out.append(s)
        return
    for k in ("data", "span", "record", "body"):
        if isinstance(obj.get(k), dict):
            _walk(obj[k], out)


def read_spans(path: Path) -> tuple:
    """(spans, stats). Unparseable lines are counted, never fatal."""
    spans, bad, lines = [], 0, 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            lines += 1
            try:
                _walk(json.loads(line), spans)
            except ValueError:
                bad += 1
    return spans, {"lines": lines, "unparseable_lines": bad}


# ---------------------------------------------------------------- aggregation

def _ancestors(span, by_id):
    seen, cur = set(), span
    while cur and cur["parent"] and cur["parent"] not in seen:
        seen.add(cur["parent"])
        cur = by_id.get(cur["parent"])
        if cur:
            yield cur


def aggregate(spans: list, services=None) -> dict:
    """{"usage": [group...], "turns": [root invoke_agent span...]} - one usage group per
    (root agent run, nearest agent, model). Tokens come from `chat` spans only (leaf calls), so a
    parent invoke_agent's own totals are never added on top of its children."""
    if services:
        spans = [s for s in spans if s["service"] in services]
    by_id = {s["span"]: s for s in spans if s["span"]}
    groups, turns = {}, []
    for s in spans:
        if s["op"] == "invoke_agent" and not any(a["op"] == "invoke_agent" for a in _ancestors(s, by_id)):
            turns.append(s)
        if s["op"] != "chat" or (s["tin"] is None and s["tout"] is None):
            continue
        anc = [a for a in _ancestors(s, by_id) if a["op"] == "invoke_agent"]
        agent = (anc[0]["agent"] if anc else None) or "?"
        root = (anc[-1]["span"] if anc else None) or s["trace"] or s["span"]
        conv = s["conv"] or next((a["conv"] for a in anc if a["conv"]), None)
        g = groups.setdefault((root, agent, s["model"]), {
            "root": root, "agent": agent, "model": s["model"], "conv": conv, "tin": 0, "tout": 0,
            "calls": 0, "start": s["start"], "end": s["end"]})
        g["tin"] += s["tin"] or 0
        g["tout"] += s["tout"] or 0
        g["calls"] += 1
        g["start"], g["end"] = min(g["start"], s["start"]), max(g["end"], s["end"])
        g["conv"] = g["conv"] or conv
    return {"usage": list(groups.values()), "turns": turns}


def _group_id(g) -> str:
    return "otel-" + hashlib.sha1(f"{g['root']}|{g['agent']}|{g['model']}".encode()).hexdigest()[:12]


def _overlap_ratio(s_start, s_end, entry) -> float:
    a, b = parse_ts(entry["start"]), parse_ts(entry["end"])
    inter = (min(s_end, b) - max(s_start, a)).total_seconds()
    dur = max((s_end - s_start).total_seconds(), 1e-9)
    return max(0.0, inter) / dur


# ---------------------------------------------------------------- story import

def import_into_story(story: dict, cfg=None, path: Path = None, force: bool = False) -> dict:
    """Idempotent: re-running (or late-arriving spans) only replaces the affected usage entries."""
    cfg = cfg or load_config()
    path = path or otel_path(cfg)
    if not path.exists():
        return {"ok": False, "reason": "otel_file_missing", "file": str(path)}
    st = path.stat()
    meta = story.setdefault("otel", {})
    if not force and meta.get("size") == st.st_size and meta.get("mtime") == st.st_mtime:
        return {"ok": True, "skipped": "unchanged"}
    spans, stats = read_spans(path)
    agg = aggregate(spans, cfg["otel"].get("service_names") or None)
    existing = {x["id"]: x for x in story["effort"]}
    changed = 0
    for g in agg["usage"]:
        eid = _group_id(g)
        stage = stage_at(story, g["start"])
        old = existing.get(eid)
        if old and old.get("tokens_in") == g["tin"] and old.get("tokens_out") == g["tout"] and \
                old.get("stage") == (stage or "unassigned"):
            continue
        E.add_entry(story, session_id=g["conv"] or g["root"], stage=stage, kind="usage",
                    start=g["start"], end=g["end"], agent=g["agent"], model=g["model"],
                    tokens_in=g["tin"], tokens_out=g["tout"], token_source="otel", cfg=cfg,
                    entry_id=eid, note=f"otel:{g['calls']} calls")
        changed += 1
    turn_entries = 0
    if cfg["otel"].get("import_turn_time"):
        for t in agg["turns"]:
            eid = "otel-turn-" + str(t["span"])
            if eid in existing:
                continue
            others = [x for x in story["effort"] if x["kind"] == "ai" and not x["id"].startswith("otel-turn-")]
            if any(_overlap_ratio(t["start"], t["end"], x) >= 0.5 for x in others):
                continue  # a hook/turn-call already timed this turn; never double count
            E.add_entry(story, session_id=t["conv"] or t["trace"], stage=stage_at(story, t["start"]),
                        kind="ai", start=t["start"], end=t["end"], agent=t["agent"] or "orchestrator",
                        cfg=cfg, entry_id=eid, note="otel_invoke_agent")
            turn_entries += 1
    meta.update({"file": str(path), "size": st.st_size, "mtime": st.st_mtime, "last_import": iso(),
                 "spans": len(spans), **stats})
    return {"ok": True, "spans": len(spans), "usage_entries_changed": changed,
            "turn_time_entries_added": turn_entries, **stats}


# ---------------------------------------------------------------- spike helper

def check(path: Path = None, cfg=None) -> dict:
    """What does a real export file contain? Use this to validate the reader against your install."""
    cfg = cfg or load_config()
    path = path or otel_path(cfg)
    if not path.exists():
        return {"ok": False, "file": str(path), "reason": "file_missing",
                "next": "Enable the file exporter (docs/mda/otel-setup.md), run one Copilot turn, re-run."}
    spans, stats = read_spans(path)
    agg = aggregate(spans)
    chats = [s for s in spans if s["op"] == "chat"]
    keys = sorted({k for s in spans for k in s["attr_keys"]})
    return {"ok": bool(chats) and any(s["tin"] is not None for s in chats), "file": str(path),
            "bytes": path.stat().st_size, **stats, "spans_read": len(spans),
            "chat_spans": len(chats), "invoke_agent_spans": sum(1 for s in spans if s["op"] == "invoke_agent"),
            "chat_with_tokens": sum(1 for s in chats if s["tin"] is not None),
            "services": sorted({s["service"] for s in spans if s["service"]}),
            "agents": sorted({s["agent"] for s in spans if s["agent"]}),
            "models": sorted({s["model"] for s in spans if s["model"]}),
            "conversations": len({s["conv"] for s in spans if s["conv"]}),
            "usage_groups": len(agg["usage"]), "root_turns": len(agg["turns"]),
            "total_tokens_in": sum(g["tin"] for g in agg["usage"]),
            "total_tokens_out": sum(g["tout"] for g in agg["usage"]),
            "token_or_cache_attrs_seen": [k for k in keys if any(t in k for t in ("token", "cache", "reasoning"))],
            "warnings": ([] if chats else ["no chat spans found: check the exporter type/path and the line format"])
            + ([] if stats["unparseable_lines"] == 0 else [f"{stats['unparseable_lines']} lines were not JSON"])}
