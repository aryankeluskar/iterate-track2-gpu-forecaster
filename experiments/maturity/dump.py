"""Dump (dev only) one row per (series, origin, horizon) with every member's quantiles, for post-hoc slicing.

Writes runs/maturity/cells.parquet: y, last value, rows at origin, headline tier at origin, activity gate [14,1],
class, and q10/q50/q90 of each `final` member (NaN where the member gave no forecast) and of drift.
Usage: PYTHONPATH=src .venv/bin/python experiments/maturity/dump.py
"""
import os
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
import pandas as pd

from gpuf import data, harness, methods
from gpuf.methods.allrental import gated, n_changes
from gpuf.methods.final import MEMBERS
from gpuf.scoring import score_fast

H = (1, 3, 7)
t0 = time.time()
U_ALL, HEAD = data.universe("rental_all"), set(data.universe("rental_headline"))
store = data.load_store(data.series_path())
cat = data.load_catalog()
meta = harness.static_meta(cat)
S = pd.read_csv(data.series_path(), dtype={"series_id": str}, low_memory=False)
S = S[S["series_id"].isin(set(cat.loc[cat["table"] == "daily_statistics", "series_id"]))].dropna(subset=["value"]).copy()
S["day"] = pd.to_datetime(S["date"]).map(pd.Timestamp.toordinal).astype(np.int64)
G = {s: g.sort_values("day") for s, g in S.groupby("series_id")}


def tier_at(s, d):
    g = G.get(s)
    if g is None:
        return False
    h = g[g["day"] <= d]
    if len(h) < 60 or d - int(h["day"].iloc[-1]) > 3:
        return False
    if h.loc[h["day"] > d - 90, "value"].round(6).nunique() < 5:
        return False
    p = pd.to_numeric(h["n_providers"], errors="coerce").dropna()
    return bool(len(p)) and p.median() >= 3


f = methods.get("final", record=True)
run = harness.evaluate(f, "dev", "rental_all", name="final", params={"record": True})
drift = harness.evaluate(methods.get("drift"), "dev", "rental_all", name="drift").cells
rows = []
for (s, o), outs in f.outs.items():
    d, v = store.history(s, o)
    last = float(v[-1])
    base = dict(series_id=s, origin_day=o, rows=len(v), span=int(o - d[0]), tier=tier_at(s, o), in37=s in HEAD,
                gate14=bool(gated(d, v, o, 14, 1)), chg14=n_changes(d, v, o, 14), chg30=n_changes(d, v, o, 30),
                cls=meta.get(s, {}).get("instrument_class", ""), last=last)
    for h in H:
        r = dict(base, horizon_days=h)
        for m in MEMBERS:
            q = outs[m][h] if outs[m] is not None and h in outs[m] else (np.nan,) * 3
            r[f"{m}_q10"], r[f"{m}_q50"], r[f"{m}_q90"] = (float(x) for x in q)
        rows.append(r)
D = pd.DataFrame(rows)
key = ["series_id", "origin_day", "horizon_days"]
D = D.merge(run.cells[key + ["y", "baseline_loss", "loss"]].rename(columns={"loss": "final_loss"}), on=key, how="inner")
D = D.merge(drift[key + ["q10", "q50", "q90"]].rename(columns={"q10": "drift_q10", "q50": "drift_q50", "q90": "drift_q90"}),
            on=key, how="left")
out = data.ROOT / "runs/maturity"
out.mkdir(parents=True, exist_ok=True)
D.to_parquet(out / "cells.parquet", index=False)
print(len(D), "cells", f"{time.time() - t0:.0f}s", out / "cells.parquet")
