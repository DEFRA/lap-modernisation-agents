"""Traditional-effort estimate: person-days (PD) per delivery phase, estimated by the LLM.

There is no rate card. During /plan the LLM proposes PD per phase for delivering this story the
traditional (non-AI) way, using the discovery evidence (factor counts, code paths), the design, and
the complexity tier's day range as a sanity anchor. Every phase carries a one-sentence reason. The
developer can change any phase (with a reason) and confirms at the plan gate.

Nothing is guessed: a phase nobody estimated stays None (NEEDS INPUT). Every figure is labelled
"LLM-estimated, unvalidated" until a developer has confirmed it, and stays labelled so while any
phase is LLM-sourced.
"""
from __future__ import annotations

import copy

from .core import iso

PHASES = ("discovery", "design", "build", "test", "transition_to_live", "support")
SOURCES = ("llm", "developer")


def _empty() -> dict:
    return {"entries": {}, "phases": {p: None for p in PHASES}, "total_pd": None, "counts": None,
            "confirmed": False, "confirmed_by": None, "created_at": iso()}


def _finish(est: dict) -> dict:
    est["phases"] = {p: (est["entries"][p]["pd"] if p in est["entries"] else None) for p in PHASES}
    vals = [v for v in est["phases"].values() if v is not None]
    est["total_pd"] = round(sum(vals), 2) if vals else None
    srcs = {e["source"] for e in est["entries"].values()}
    est["method"] = "+".join(s for s in SOURCES if s in srcs) or "none"
    est["labels"] = labels(est)
    return est


def set_phase(est, phase: str, pd, reason: str, source: str = "llm", counts: dict = None) -> dict:
    """Record or replace one phase. A written reason is mandatory; any change resets confirmation."""
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}")
    try:
        pd = float(pd)
    except (TypeError, ValueError):
        raise ValueError(f"{phase}: pd must be a number")
    if pd < 0:
        raise ValueError(f"{phase}: pd must be non-negative")
    if not (reason or "").strip():
        raise ValueError(f"{phase}: a written reason is required")
    est = est or _empty()
    prev = est["entries"].get(phase)
    est["entries"][phase] = {"pd": round(pd, 2), "reason": reason.strip(), "source": source, "at": iso(),
                             "previous_pd": prev["pd"] if prev else None}
    if counts is not None:
        est["counts"] = counts
    est["confirmed"], est["confirmed_by"] = False, None
    return _finish(est)


def set_many(est, items: dict, source: str = "llm", counts: dict = None) -> dict:
    """items: {phase: {"pd": n, "reason": "..."}}. All-or-nothing: one bad phase rejects the batch."""
    if not isinstance(items, dict) or not items:
        raise ValueError('expected {"phase": {"pd": n, "reason": "..."}, ...}')
    staged = copy.deepcopy(est) if est else None
    for phase, v in items.items():
        if not isinstance(v, dict):
            raise ValueError(f"{phase}: expected {{\"pd\": n, \"reason\": \"...\"}}")
        staged = set_phase(staged, phase, v.get("pd"), v.get("reason"), source, counts)
    return staged


def confirm(est: dict, by: str) -> dict:
    est["confirmed"], est["confirmed_by"], est["confirmed_at"] = True, by, iso()
    est["labels"] = labels(est)
    return est


def labels(est: dict) -> list:
    out = []
    if any(e["source"] == "llm" for e in est.get("entries", {}).values()):
        out.append("LLM-estimated, unvalidated (no rate card): internal use only")
    if not est.get("confirmed"):
        out.append("not yet confirmed by the developer")
    return out
