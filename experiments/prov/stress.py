"""Part 3: synthetic trend-reversal stress test on dev second-half origins (rows <= 2026-10-13 only).
For each cell whose middle offer belongs to a dynamic provider (trailing 21-day reprice rate > 0.5), that provider's
offers in the actual target-day panel are repriced counterfactually from their origin-day price:
  flat      price stays at the origin price
  reverse   price moves at minus the provider's trailing 21-day mean daily log change (same speed, opposite sign)
  mirror    price = origin price^2 / actual target price (the realised path reflected)
Other offers keep their actual target-day prices. Truth = actual y x counterfactual median / actual median.
Forecasts are unchanged (they use rows <= origin only); only the truth they are scored against changes."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from score import ref, rescore
from gpuf import panel as P
from gpuf.methods import prov as PR

K = ["series_id", "origin_day", "horizon_days"]
W, THR = 21, 0.5
prov_stats, _ = PR._prep()


def rate_drift(src, pv, o):
    x = prov_stats.get((src, pv))
    if x is None:
        return 0.0, 0.0
    d, n, k, mr = x
    s = (d <= o) & (d > o - W)
    return (float(k[s].sum() / n[s].sum()), float((k[s] * mr[s]).sum() / n[s].sum())) if s.any() else (0.0, 0.0)


def pinloss(c, y):
    pin = lambda f, t: np.maximum(t * (y - f), (t - 1) * (y - f))
    return (pin(c.q10.to_numpy(), .1) + pin(c.q50.to_numpy(), .5) + pin(c.q90.to_numpy(), .9)) / 3


runs = {"prov": pd.read_parquet(sys.argv[1] if len(sys.argv) > 1 else "runs/prov/L1_W21_gdyn.parquet"), "mix": ref("mix")}
runs["blend"] = rescore(runs["prov"].merge(runs["mix"][K + ["q10", "q50", "q90"]], on=K, suffixes=("", "_b")).pipe(
    lambda m: m.assign(**{q: np.exp(0.5 * np.log(m[q]) + 0.5 * np.log(m[q + "_b"])) for q in ("q10", "q50", "q90")})))
base = runs["mix"].sort_values(K).reset_index(drop=True)
mid_day = np.sort(base.origin_day.unique())[len(base.origin_day.unique()) // 2]
rows, prov_of = [], {}
for (sid, o), g in base[base.origin_day >= mid_day].groupby(["series_id", "origin_day"]):
    if not P.supported(sid):
        continue
    src = sid.split(".")[0]
    allr = P.offers(sid, o + 7) if False else P._index()[P.parse_sid(sid)]
    po = allr[allr.day == o].sort_values("price")
    if po.empty:
        continue
    n = len(po)
    mids = po.iloc[[(n - 1) // 2, n // 2]].provider.unique()
    rd = {pv: rate_drift(src, pv, o) for pv in mids}
    pv = max(rd, key=lambda p: rd[p][0])
    if rd[pv][0] <= THR:
        continue
    p0 = po.set_index("key").price
    for _, r in g.iterrows():
        h, T = int(r.horizon_days), int(r.origin_day + r.horizon_days)
        pt = allr[allr.day == T]
        if pt.empty:
            continue
        act = float(np.median(pt.price))
        out = {"series_id": sid, "origin_day": o, "horizon_days": h, "provider": pv, "drift": rd[pv][1]}
        for sc in ("flat", "reverse", "mirror"):
            px = pt.price.to_numpy().copy()
            for i, (key, prv, price) in enumerate(zip(pt.key, pt.provider, pt.price)):
                if prv == pv and key in p0.index:
                    px[i] = {"flat": p0[key], "reverse": p0[key] * np.exp(-rd[pv][1] * h), "mirror": p0[key] ** 2 / price}[sc]
            out[sc] = float(r.y) * float(np.median(px)) / act
        rows.append(out)
S = pd.DataFrame(rows)
res = {"n_cells": len(S), "providers": S.provider.value_counts().to_dict(), "mean_trailing_drift_%/day": round(100 * S.drift.mean(), 3),
       "share_of_truth_changed": {sc: round(float((S[sc] != base.merge(S[K], on=K).y.values).mean()), 3) for sc in ("flat", "reverse", "mirror")}}
Btot = base.baseline_loss.sum()
for sc in ("actual", "flat", "reverse", "mirror"):
    r = {}
    for nm, c in runs.items():
        c = c.sort_values(K).reset_index(drop=True)
        m = c.merge(S[K + ["flat", "reverse", "mirror"]], on=K, how="left")
        sel = m.flat.notna().to_numpy()
        y = m.y.to_numpy().copy()
        if sc != "actual":
            y[sel] = m[sc].to_numpy()[sel]
        loss = pinloss(m, y)
        bl = (lambda b: (np.maximum(.1 * (y - b), -.9 * (y - b)) + .5 * np.abs(y - b) + np.maximum(.9 * (y - b), -.1 * (y - b))) / 3)(m.baseline.to_numpy())
        r[nm] = {"pooled_skill": round(1 - loss.sum() / bl.sum(), 4), "stressed_cells_skill": round(1 - loss[sel].sum() / bl[sel].sum(), 4),
                 "stressed_loss": round(float(loss[sel].sum()), 3), "stressed_lv_loss": round(float(bl[sel].sum()), 3)}
    r["prov_minus_mix_pooled"] = round(r["prov"]["pooled_skill"] - r["mix"]["pooled_skill"], 4)
    r["blend_minus_mix_pooled"] = round(r["blend"]["pooled_skill"] - r["mix"]["pooled_skill"], 4)
    res[sc] = r
by = []
for nm, c in runs.items():
    m = S.merge(c[K + ["q10", "q50", "q90", "y", "baseline"]], on=K)
    for sc in ("actual", "flat", "reverse", "mirror"):
        y = m.y.to_numpy() if sc == "actual" else m[sc].to_numpy()
        by.append(m[["provider", "horizon_days"]].assign(method=nm, sc=sc, loss=pinloss(m, y)))
by = pd.concat(by).pivot_table(index=["provider", "horizon_days", "sc"], columns="method", values="loss", aggfunc="sum")
by["prov/mix"] = by.prov / by.mix; by["blend/mix"] = by.blend / by.mix
res["loss_ratio_by_provider_h"] = {f"{p}|h{h}|{sc}": [round(v, 3) for v in r[["prov/mix", "blend/mix"]]] for (p, h, sc), r in by.iterrows()}
print(by.round(3).to_string())
print(json.dumps({k: v for k, v in res.items() if k != "loss_ratio_by_provider_h"}, indent=1))
json.dump(res, open("experiments/prov/results/stress.json", "w"), indent=1)
