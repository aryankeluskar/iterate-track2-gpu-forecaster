"""python -m gpuf.run --method drift --split dev --universe rental_headline [--params JSON] [--official]

Prints one JSON line and appends it to data_out/trajectory.jsonl.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid

from . import compare, data, harness, methods

TRAJECTORY = data.DATA_OUT / "trajectory.jsonl"


def git_sha() -> str:
    r = subprocess.run(["git", "-C", str(data.ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    sha = r.stdout.strip() or "none"
    dirty = subprocess.run(["git", "-C", str(data.ROOT), "status", "--porcelain", "--", "src"],
                           capture_output=True, text=True).stdout.strip()
    return sha + ("-dirty" if dirty else "")


def _r(x, nd=6):
    return None if x is None else round(float(x), nd)


def run(method: str, split: str, universe: str, params: dict | None = None, unlock_test: bool = False,
        official: bool = False, log: bool = True) -> dict:
    params = params or {}
    t0 = time.time()
    res = harness.evaluate(methods.get(method, **params), split, universe, name=method, params=params,
                           unlock_test=unlock_test)
    s = res.summary
    rec = {"experiment_id": f"{time.strftime('%Y%m%dT%H%M%S')}-{method}-{uuid.uuid4().hex[:6]}", "method": method,
           "params": params, "split": split, "universe": universe, "pooled_skill": _r(s["pooled_skill"]),
           "pooled_loss": _r(s["pooled_loss"], 9), "baseline_loss": _r(s["baseline_loss"], 9),
           "skill_mean_of_series": s["skill_mean_of_series"], "skill_median_of_series": s["skill_median_of_series"],
           "skill_geomean": s["skill_geomean"], "coverage": _r(s["coverage"]["within_q10_q90"]) if s["coverage"] else None,
           "n_cells": s["n_cells"], "n_series": s.get("n_series", 0)}
    if method == "drift" and not params:
        rec.update(skill_vs_drift=0.0, ci90_vs_drift=[0.0, 0.0], dm_vs_drift=None)
    else:
        ref = harness.evaluate(methods.get("drift"), split, universe, name="drift",
                               params={"role": f"reference for {method}"}, unlock_test=unlock_test)
        c = compare.paired(res.cells, ref.cells)
        rec.update(skill_vs_drift=_r(c["d_pooled_skill"]), ci90_vs_drift=[_r(x) for x in c["ci90_d_pooled_skill"]],
                   dm_vs_drift=_r(c.get("dm_stat"), 3))
    if official:
        o = res.official(data.ROOT / "runs/official" / rec["experiment_id"])
        rec["official_pooled_skill"] = _r(o.get("pooled_skill"))
        rec["official_n_cells"] = o.get("n_cells")
        rec["official_agrees"] = (o.get("n_cells") == s["n_cells"] and o.get("pooled_skill") is not None
                                  and abs(o["pooled_skill"] - s["pooled_skill"]) < 1e-9)
    rec["wall_time_s"] = round(time.time() - t0, 2)
    rec["git_sha"] = git_sha()
    if log:
        TRAJECTORY.parent.mkdir(parents=True, exist_ok=True)
        with open(TRAJECTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", required=True)
    ap.add_argument("--split", default="dev", choices=["dev", "val", "test", "starter15"])
    ap.add_argument("--universe", default="rental_headline", choices=list(data.UNIVERSES))
    ap.add_argument("--params", default="{}", help="JSON dict passed to the method factory")
    ap.add_argument("--unlock-test", action="store_true", help="required for --split test (logged)")
    ap.add_argument("--official", action="store_true", help="also score with starter/scorer.py and check agreement")
    ap.add_argument("--no-log", action="store_true", help="do not append to data_out/trajectory.jsonl")
    a = ap.parse_args()
    rec = run(a.method, a.split, a.universe, json.loads(a.params), a.unlock_test, a.official, not a.no_log)
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
