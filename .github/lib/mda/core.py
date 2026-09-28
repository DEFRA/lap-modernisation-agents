"""Paths, config, time and atomic JSON helpers shared by every MDA module."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import tempfile
from pathlib import Path

DEFAULT_CONFIG = {
    "ado": {
        "org_url": "",  # e.g. https://dev.azure.com/<org>  (env MDA_ADO_ORG_URL overrides)
        "project": "",  # falls back to the story's captured project name
        "api_version": "7.1",
        "effort_record_type": "Task",
        "record_tag": "MDA-EffortRecord",
        "structured_fields": True,  # falls back to payload-only if fields are missing
        "wiki_id": "",
        "wiki_report_path": "/Migration-Delivery/Effort-Reports",
        "fields": {
            "key": "Custom.MDARecordKey", "project": "Custom.MDAProject",
            "story_id": "Custom.MDAStoryId", "sprint": "Custom.MDASprint",
            "cycle": "Custom.MDACycle", "stage": "Custom.MDAStage",
            "phase": "Custom.MDAPhase", "trigger": "Custom.MDATrigger",
            "factors": "Custom.MDAFactors", "weights": "Custom.MDAWeights",
            "tier": "Custom.MDATier", "traditional_days": "Custom.MDATraditionalDays",
            "effort_hours": "Custom.MDAActiveEffortHours",
            "calendar_hours": "Custom.MDACalendarHours", "developer": "Custom.MDADeveloper",
            "tokens": "Custom.MDATokens", "recorded_at": "Custom.MDARecordedAt",
            "payload": "Custom.MDAPayload",
        },
    },
    "sync": {
        "check_every_n_prompts": 10,
        "heartbeat_seconds": 300,
        "http_timeout_seconds": 6,
        "hook_http_timeout_seconds": 4,
    },
    "pat": {"warn_days": 7},
    "effort": {
        "approval_gap_cap_minutes": 120,  # cap on (approval - last response); flagged when hit
        "turn_cap_minutes": 120,          # cap on a single agent turn; flagged when hit
        "hours_per_day": 7.5,
        "timezone": "",                   # IANA name; empty = machine local time
    },
    "gates": {
        "self_heal_max_retries": 3,       # OPEN GOVERNANCE ITEM (spec s15): not yet fixed
        "max_forced_continuations": 2,
    },
    "sprints": [],  # [{"name": "Sprint 12", "start": "2026-09-01", "end": "2026-09-14"}]
    "sonar": {"organization": "", "project_key": "", "host": "https://sonarcloud.io"},
    "usage": {"sync_every_hours": 24},
}


def repo_root() -> Path:
    env = os.environ.get("MDA_ROOT")
    if env:
        return Path(env).resolve()
    here = Path.cwd().resolve()
    for c in [here, *here.parents]:
        if (c / ".git").exists():
            return c
    return here


def store_dir() -> Path:
    d = repo_root() / ".mda"
    d.mkdir(parents=True, exist_ok=True)
    return d


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    root = repo_root()
    for p in (root / ".github/config/mda/mda.config.json", root / ".mda/config.local.json"):
        if p.exists():
            try:
                cfg = deep_merge(cfg, json.loads(p.read_text(encoding="utf-8-sig")))
            except (OSError, ValueError):
                pass
    if os.environ.get("MDA_ADO_ORG_URL"):
        cfg["ado"]["org_url"] = os.environ["MDA_ADO_ORG_URL"]
    if os.environ.get("MDA_ADO_PROJECT"):
        cfg["ado"]["project"] = os.environ["MDA_ADO_PROJECT"]
    cfg["ado"]["org_url"] = cfg["ado"]["org_url"].rstrip("/")
    return cfg


# ---------------------------------------------------------------- time

def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(t: dt.datetime | None = None) -> str:
    return (t or utcnow()).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_ts(v) -> dt.datetime:
    """Accepts ISO strings, epoch seconds or epoch millis; falls back to now."""
    if v is None or v == "":
        return utcnow()
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit()):
            n = float(v)
            if n > 1e11:
                n /= 1000.0
            return dt.datetime.fromtimestamp(n, dt.timezone.utc)
        s = str(v).replace("Z", "+00:00")
        t = dt.datetime.fromisoformat(s)
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except (ValueError, OverflowError, OSError):
        return utcnow()


def local_tz(cfg: dict | None = None):
    name = ((cfg or load_config())["effort"].get("timezone") or "").strip()
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception:
            pass
    return dt.datetime.now().astimezone().tzinfo


# ---------------------------------------------------------------- json

def _digest(obj: dict) -> str:
    body = {k: v for k, v in obj.items() if k != "_sha"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def write_json(path: Path, obj: dict, checksum: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if checksum:
        obj["_sha"] = _digest(obj)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, default=str)
        if path.exists():
            try:
                (path.with_suffix(path.suffix + ".bak")).write_bytes(path.read_bytes())
            except OSError:
                pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path: Path, checksum: bool = True):
    """Returns (obj|None, status) where status is ok | missing | corrupt."""
    if not path.exists():
        return None, "missing"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "corrupt"
    if not isinstance(obj, dict):
        return None, "corrupt"
    if checksum and obj.get("_sha") and obj["_sha"] != _digest(obj):
        return None, "corrupt"
    return obj, "ok"
