"""Dev only. Score one hazard variant, save its cells and classifier log, report classifier quality.

Usage: PYTHONPATH=src .venv/bin/python experiments/hazard/analyze.py TAG 'PARAMS_JSON'
Writes runs/hazard/cells_TAG.parquet, runs/hazard/clf_TAG.parquet and prints the classifier report.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf import harness, methods

U = "rental_headline"
OUT = Path("runs/hazard"); OUT.mkdir(parents=True, exist_ok=True)
tag, params = sys.argv[1], json.loads(sys.argv[2])
if "--cached" in sys.argv:
    L = pd.read_parquet(OUT / f"clf_{tag}.parquet")
else:
    f = methods.get("hazard", **params)
    res = harness.evaluate(f, "dev", U, name="hazard", params=params)
    cells = res.cells
    cells.to_parquet(OUT / f"cells_{tag}.parquet")
    L = pd.DataFrame(f.log, columns=["series_id", "origin_day", "horizon_days", "p0", "pu", "pd", "b0", "bu", "bd", "o0", "ou", "od"])
    L = L.merge(cells[["series_id", "origin_day", "horizon_days", "y", "baseline", "source_id"]],
                on=["series_id", "origin_day", "horizon_days"])
    r = np.log(L.y / L.baseline)
    L["cls"] = np.where(r > 1e-9, 1, np.where(r < -1e-9, 2, 0))
    L.to_parquet(OUT / f"clf_{tag}.parquet")
    print("pooled skill", round(res.summary["pooled_skill"], 4))


def auc(s, y):
    from sklearn.metrics import roc_auc_score
    return roc_auc_score(y, s) if 0 < y.mean() < 1 else np.nan


def metrics(g):
    P = g[["p0", "pu", "pd"]].to_numpy().clip(1e-6); B = g[["b0", "bu", "bd"]].to_numpy().clip(1e-6)
    O = g[["o0", "ou", "od"]].to_numpy().clip(1e-6)
    Y = np.eye(3)[g.cls.to_numpy()]
    mv = (g.cls > 0).to_numpy()
    o = {"n": len(g), "move_rate": mv.mean(),
         "brier": ((P - Y) ** 2).sum(1).mean(), "brier_base": ((B - Y) ** 2).sum(1).mean(),
         "logloss": -np.log((P * Y).sum(1)).mean(), "logloss_base": -np.log((B * Y).sum(1)).mean(),
         "brier_own": ((O - Y) ** 2).sum(1).mean(), "logloss_own": -np.log((O * Y).sum(1)).mean(),
         "auc_move_own": auc(1 - g.o0.to_numpy(), mv),
         "auc_move": auc(1 - g.p0.to_numpy(), mv)}
    if mv.sum() > 5:
        gm = g[mv]
        o["auc_up_dn"] = auc((gm.pu / (gm.pu + gm.pd)).to_numpy(), (gm.cls == 1).to_numpy())
        o["up_share"] = (gm.cls == 1).mean()
    return pd.Series(o)


pd.set_option("display.width", 250)
print("\nclassifier, out of sample by origin (all headline dev cells):")
print(metrics(L).round(4).to_string())
print("\nby collector x horizon:")
print(L.groupby(["source_id", "horizon_days"]).apply(metrics).round(3).to_string())
print("\nby horizon:")
print(L.groupby("horizon_days").apply(metrics).round(3).to_string())
L["pm"] = 1 - L.p0
L["bin"] = pd.cut(L.pm, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0], include_lowest=True)
print("\nreliability of P(move):")
print(L.groupby("bin", observed=True).agg(n=("pm", "size"), pred=("pm", "mean"), obs=("cls", lambda c: (c > 0).mean()),
                                          base_pred=("b0", lambda b: 1 - b.mean()), own_pred=("o0", lambda b: 1 - b.mean())).round(3).to_string())
M = L[L.cls > 0].assign(pup=lambda d: d.pu / (d.pu + d.pd))
M["bin"] = pd.cut(M.pup, [0, .2, .4, .6, .8, 1.0], include_lowest=True)
print("\nreliability of P(up | move):")
print(M.groupby("bin", observed=True).agg(n=("pup", "size"), pred=("pup", "mean"), obs=("cls", lambda c: (c == 1).mean())).round(3).to_string())
