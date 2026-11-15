"""Late-window check (EVAL_PROTOCOL.md Amendment 4): the origins 31 October to 5 November 2026, which no split holds.

Reporting only. Scores the submitted forecaster exactly as `bash reproduce.sh final` configures it (seven members,
activity gate [14, 1] on non-headline series, analog cap 2026-11-06), the reference `mix` and the starter `drift`,
on every posted rental series, at horizons 1, 3 and 7 where the target date is on or before 6 November (the pack's
last day: h=1 from all six origins, h=3 from 31 Oct to 3 Nov, no h=7). Nothing here changes the submission.

  PYTHONPATH=src .venv/bin/python experiments/late/run.py build    # pretrained members per origin (torch, own processes)
  PYTHONPATH=src .venv/bin/python experiments/late/run.py score    # final, mix, drift; writes results/
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = Path(__file__).resolve().parent / "results"
ORIGINS = ["2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
CAP = "2026-11-06"
FINAL = {"members": ["mix", "gbm", "chronos", "analog", "prov", "fm2", "fragility"], "gate": [14, 1],
         "gate_scope": "nonhead", "cap": CAP, "universe": "rental_all"}


def build():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "OMP_NUM_THREADS": "2", "HF_HUB_OFFLINE": "1"}
    for o in ORIGINS:
        subprocess.run([sys.executable, "-B", "-m", "gpuf.final_build", "--origin", o, "--universe", "rental_all"],
                       env=env, cwd=ROOT, check=True)


def pooled(c):
    b = c["baseline_loss"].sum()
    return float(1 - c["loss"].sum() / b) if b > 0 else float("nan")


def summary(c):
    return {"cells": int(len(c)), "series": int(c["series_id"].nunique()), "pooled_skill": round(pooled(c), 4),
            "loss": round(float(c["loss"].sum()), 6), "baseline_loss": round(float(c["baseline_loss"].sum()), 6),
            "coverage": round(float(((c["y"] >= c["q10"]) & (c["y"] <= c["q90"])).mean()), 4),
            "above_q90": round(float((c["y"] > c["q90"]).mean()), 4),
            "below_q10": round(float((c["y"] < c["q10"]).mean()), 4)}


def score():
    from gpuf import data, harness, methods
    from gpuf.data import starter_common as sc
    head = set(data.universe("rental_headline"))
    systems = {"drift": lambda o: methods.get("drift"), "mix": lambda o: methods.get("mix", **methods_final_mix()),
               "final": lambda o: methods.get("final", **{**FINAL, "tag": o})}
    cells = []
    for name, mk in systems.items():
        for o in ORIGINS:
            r = harness.evaluate(mk(o), [sc.day_of(sc.parse_date(o))], universe="rental_all", horizons=(1, 3, 7),
                                 name=f"late_{name}")
            c = r.cells.copy()
            c["system"] = name
            cells.append(c)
    cells = pd.concat(cells, ignore_index=True)
    cells["universe"] = np.where(cells["series_id"].isin(head), "headline", "non_headline")
    keep = ["system", "universe", "series_id", "origin_date", "horizon_days", "y", "baseline", "q10", "q50", "q90",
            "loss", "baseline_loss"]
    OUT.mkdir(parents=True, exist_ok=True)
    cells[keep].to_csv(OUT / "cells.csv", index=False)
    # common keys: every system must have every cell (the harness fills missing horizons with last value)
    k = cells.groupby(["universe", "series_id", "origin_date", "horizon_days"])["system"].nunique()
    assert (k == len(systems)).all(), "systems do not share cells"
    res = {}
    for u, cu in list(cells.groupby("universe")) + [("all", cells)]:
        res[u] = {s: summary(cs) for s, cs in cu.groupby("system")}
        res[u]["by_horizon"] = {f"h{h}": {s: round(pooled(x), 4) for s, x in ch.groupby("system")}
                                for h, ch in cu.groupby("horizon_days")}
        res[u]["by_origin"] = {o: {s: round(pooled(x), 4) for s, x in co.groupby("system")}
                               for o, co in cu.groupby("origin_date")}
        w = cu.pivot_table(index=["series_id", "origin_date", "horizon_days"], columns="system", values="loss")
        b = cu[cu.system == "final"].set_index(["series_id", "origin_date", "horizon_days"])["baseline_loss"]
        # paired difference in pooled skill = (loss_other - loss_final) / baseline, per origin
        d = (w.sub(w["final"], axis=0)).join(b)
        res[u]["final_minus"] = {s: round(float(d[s].sum() / d["baseline_loss"].sum()), 4) for s in ("drift", "mix")}
        res[u]["final_minus_by_origin"] = {o: {s: round(float(g[s].sum() / g["baseline_loss"].sum()), 4)
                                               if g["baseline_loss"].sum() > 0 else None for s in ("drift", "mix")}
                                           for o, g in d.groupby(level="origin_date")}
    json.dump(res, open(OUT / "late.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


def methods_final_mix():
    from gpuf.methods.final import REF_MIX
    return REF_MIX


if __name__ == "__main__":
    {"build": build, "score": score}[sys.argv[1]]()
