"""Score panel variants on dev headline against drift and mix, with breakdowns.

Usage: PYTHONPATH=src .venv/bin/python experiments/panel/score.py NAME METHOD 'PARAMS_JSON'
Writes runs/panel/<NAME>.parquet (cells) and appends a summary line to experiments/panel/results/scores.jsonl.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf import compare, harness, methods

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs/panel"
MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]


def cells(name, method, params):
    p = RUNS / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    t = time.time()
    c = harness.evaluate(methods.get(method, **params), "dev", "rental_headline", name=method, params=params).cells
    print(f"[{name}] eval {time.time() - t:.0f}s", file=sys.stderr)
    RUNS.mkdir(parents=True, exist_ok=True)
    c.to_parquet(p)
    return c


def bucket(c):
    r = np.log(c["y"] / c["baseline"])
    return np.select([r == 0, r.abs() < 0.01, r.abs() <= 0.05, r > 0.05], ["none", "<1%", "1-5%", "up>5%"], "down>5%")


def report(name, method, params):
    a = cells(name, method, params)
    d = cells("drift", "drift", {})
    m = cells("mix", *MIX)
    B = a["baseline_loss"].sum()
    out = {"name": name, "method": method, "params": params, "n_cells": len(a),
           "skill": round(1 - a["loss"].sum() / B, 4),
           "coverage": round(float(((a.y >= a.q10) & (a.y <= a.q90)).mean()), 3)}
    for ref, rc in (("drift", d), ("mix", m)):
        c = compare.paired(a, rc)
        out[f"d_vs_{ref}"] = round(c["d_pooled_skill"], 4)
        out[f"ci90_vs_{ref}"] = [round(x, 4) for x in c["ci90_d_pooled_skill"]]
    base_q50 = (a["y"] - a["baseline"]).abs() * 0.5
    out["q50_loss_ratio_vs_last"] = round(float(a["loss_q50"].sum() / base_q50.sum()), 4)
    h7 = a[a.horizon_days == 7]
    out["h7_above_q90"] = round(float((h7.y > h7.q90).mean()), 3)
    out["h7_below_q10"] = round(float((h7.y < h7.q10).mean()), 3)
    j = a.merge(m[compare.KEY + ["loss"]], on=compare.KEY, suffixes=("", "_mix")).merge(
        d[compare.KEY + ["loss"]].rename(columns={"loss": "loss_drift"}), on=compare.KEY)
    j["bucket"] = bucket(j)
    for col in ("source_id", "horizon_days", "bucket"):
        out[f"gain_vs_mix_by_{col}"] = {str(k): round(float((v.loss_mix.sum() - v.loss.sum()) / B), 4) for k, v in j.groupby(col)}
        out[f"gain_vs_drift_by_{col}"] = {str(k): round(float((v.loss_drift.sum() - v.loss.sum()) / B), 4) for k, v in j.groupby(col)}
    s = j.groupby("series_id").apply(lambda v: (v.loss_mix.sum() - v.loss.sum()) / B, include_groups=False).sort_values()
    out["top_series_vs_mix"] = {k.split(".", 1)[1][:40]: round(float(v), 4) for k, v in pd.concat([s.head(3), s.tail(3)]).items()}
    print(json.dumps(out))
    with open(ROOT / "experiments/panel/results/scores.jsonl", "a") as f:
        f.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    report(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})
