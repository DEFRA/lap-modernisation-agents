"""Complexity scoring (spec s8): store raw factor counts + weights, not just the tier."""
from __future__ import annotations

import csv
import json
import math

from .core import iso, repo_root

MODEL_PATH = ".github/config/mda/complexity-model.json"


def load_model(path=None) -> dict:
    p = repo_root() / (path or MODEL_PATH)
    return json.loads(p.read_text(encoding="utf-8-sig"))


def validate_counts(counts: dict, model: dict) -> dict:
    unknown = [k for k in counts if k not in model["weights"]]
    if unknown:
        raise ValueError(f"unknown factors {unknown}; valid: {sorted(model['weights'])}")
    clean = {}
    for k in model["weights"]:
        v = counts.get(k, 0)
        if not isinstance(v, (int, float)) or v < 0:
            raise ValueError(f"factor '{k}' must be a non-negative number, got {v!r}")
        clean[k] = v
    return clean


def tier_for(score: float, model: dict) -> dict:
    for b in model["bands"]:
        if b["max_score"] is None or score <= b["max_score"]:
            return b
    return model["bands"][-1]


def score(counts: dict, model: dict = None) -> dict:
    model = model or load_model()
    counts = validate_counts(counts, model)
    pts = {k: round(counts[k] * model["weights"][k], 4) for k in counts}
    total = round(sum(pts.values()), 4)
    b = tier_for(total, model)
    lo, hi = b["days_low"], b["days_high"]
    point = (lo + hi) / 2 if hi is not None else lo  # open-ended band: use the lower bound
    return {
        "model_version": model["model_version"], "calibrated": model["calibrated"],
        "counts": counts, "weights": dict(model["weights"]), "points_by_factor": pts,
        "score": total, "tier": b["tier"],
        "traditional_days": {"low": lo, "high": hi, "point": point},
        "efficiency_assumed": b["efficiency"], "baseline_efficiency": model["baseline_efficiency"],
        "expected_agentic_days": round(point * (1 - b["efficiency"]), 2),
        "scored_at": iso(),
        "warning": None if model["calibrated"] else
        "UNCALIBRATED model: internal use only, not for client-facing reporting (spec s8.3/s15).",
    }


def apply_override(result: dict, tier: str, note: str, model: dict = None) -> dict:
    """Developer confirms or adjusts at the Architecture gate; both are recorded."""
    model = model or load_model()
    b = next((x for x in model["bands"] if x["tier"].lower() == tier.lower()), None)
    if not b:
        raise ValueError(f"tier must be one of {[x['tier'] for x in model['bands']]}")
    lo, hi = b["days_low"], b["days_high"]
    point = (lo + hi) / 2 if hi is not None else lo
    result = dict(result)
    result["developer_adjustment"] = {"from_tier": result["tier"], "to_tier": b["tier"],
                                      "note": note, "at": iso()}
    result.update({"tier": b["tier"], "traditional_days": {"low": lo, "high": hi, "point": point},
                   "efficiency_assumed": b["efficiency"],
                   "expected_agentic_days": round(point * (1 - b["efficiency"]), 2)})
    return result


# --------------------------------------------------------------- calibration (spec s8.3)

def _nnls(rows, y, iters=4000, lr=None):
    """Non-negative least squares by projected coordinate descent (no numpy dependency)."""
    n = len(rows[0])
    w = [0.5] * n
    col_sq = [sum(r[j] ** 2 for r in rows) or 1e-9 for j in range(n)]
    for _ in range(iters):
        delta = 0.0
        for j in range(n):
            resid = [y[i] - sum(rows[i][k] * w[k] for k in range(n)) for i in range(len(rows))]
            step = sum(rows[i][j] * resid[i] for i in range(len(rows))) / col_sq[j]
            new = max(0.0, w[j] + step)
            delta = max(delta, abs(new - w[j]))
            w[j] = new
        if delta < 1e-9:
            break
    return w


def calibrate(csv_path: str, model: dict = None, min_rows: int = 10) -> dict:
    """History CSV columns: story_id, actual_traditional_days, then one column per factor.

    Method: fit weights so that score ~ actual effort (days) by NNLS, then derive tier band
    edges from the 25/50/75th percentile of actual days. Proposes a model; never marks it
    calibrated on its own - a human reviews the fit report then runs with --accept."""
    model = model or load_model()
    factors = list(model["weights"])
    rows, y, ids = [], [], []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                rows.append([float(r.get(k) or 0) for k in factors])
                y.append(float(r["actual_traditional_days"]))
                ids.append(r.get("story_id"))
            except (KeyError, ValueError) as e:
                raise ValueError(f"bad history row {r}: {e}")
    if len(rows) < min_rows:
        raise ValueError(f"need at least {min_rows} completed stories, got {len(rows)} (spec: 10-15)")
    w = _nnls(rows, y)
    pred = [sum(a * b for a, b in zip(r, w)) for r in rows]
    mean_y = sum(y) / len(y)
    ss_res = sum((a - b) ** 2 for a, b in zip(y, pred))
    ss_tot = sum((a - mean_y) ** 2 for a in y) or 1e-9
    mape = sum(abs(a - b) / a for a, b in zip(y, pred) if a) / max(1, sum(1 for a in y if a))
    ys = sorted(y)

    def q(p):
        return ys[min(len(ys) - 1, max(0, math.ceil(p * len(ys)) - 1))]
    edges = [q(0.25), q(0.5), q(0.75)]
    scores_sorted = sorted(pred)
    sc_edges = [scores_sorted[min(len(scores_sorted) - 1, math.ceil(p * len(scores_sorted)) - 1)]
                for p in (0.25, 0.5, 0.75)]
    proposed = json.loads(json.dumps(model))
    proposed["weights"] = {k: round(v, 3) for k, v in zip(factors, w)}
    old = model["bands"]
    lows = [max(1, round(ys[0]))] + [round(e) for e in edges]
    highs = [round(e) for e in edges] + [None]
    for i, b in enumerate(proposed["bands"]):
        b["max_score"] = round(sc_edges[i], 1) if i < 3 else None
        b["days_low"], b["days_high"] = lows[i], highs[i]
        b["efficiency"] = old[i]["efficiency"]  # efficiency needs pilot data, not history CSV
    proposed["model_version"] = f"calibrated-{iso()[:10]}"
    return {"proposed_model": proposed,
            "fit": {"n": len(rows), "r_squared": round(1 - ss_res / ss_tot, 3),
                    "mape": round(mape, 3), "stories": ids},
            "method": "NNLS fit of factor counts to actual days; band edges at 25/50/75th "
                      "percentile of actual days and of fitted scores. Efficiency figures are "
                      "carried over unchanged (need pilot data, spec s8.4)."}
