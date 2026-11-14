"""Diagnostic (dev only): pooled skill of `final`, its members, mix and drift by series maturity at the origin.

Maturity: (a) the organisers' headline tier applied at the origin (experiments/audit/universe.py rule), (b) the
fixed 37 series chosen as of 2026-11-06, (c) the number of rows the series has on or before the origin.
Usage: PYTHONPATH=src .venv/bin/python experiments/maturity/diag.py > experiments/maturity/results/diag.txt
"""
import json
import os
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
import pandas as pd

from gpuf import data, harness, methods, splits
from gpuf.methods.final import MEMBERS, blend
from gpuf.scoring import score_fast

OUT = Path(__file__).resolve().parent / "results"
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
print(f"# final on dev rental_all: {len(run.cells)} cells, {time.time() - t0:.0f}s", flush=True)
hist = {k: store.history(*k) for k in f.outs}


def reblend(members):
    rows = []
    for (s, o), outs in f.outs.items():
        last = float(hist[(s, o)][1][-1])
        res, _ = blend({m: outs[m] for m in members}, H, last)
        for h in H:
            (a, b, c), _ = harness._clean(res[h], last)
            rows.append((s, o, h, a, b, c, last, 0))
    fc = pd.DataFrame(rows, columns=["series_id", "origin_day", "horizon_days", "q10", "q50", "q90", "baseline", "filled"])
    return score_fast(fc, store, U_ALL, H)[0]


C = {"final": reblend(MEMBERS), "drift": harness.evaluate(methods.get("drift"), "dev", "rental_all", name="drift").cells}
for m in MEMBERS:
    C[m] = reblend((m,))
C["orch5"] = reblend(("mix", "fm2", "analog", "prov", "fragility"))
chk = C["final"].merge(run.cells, on=["series_id", "origin_day", "horizon_days"], suffixes=("", "_h"))
assert len(chk) == len(run.cells) and np.array_equal(chk["loss"].to_numpy(), chk["loss_h"].to_numpy())

pairs = C["final"][["series_id", "origin_day"]].drop_duplicates().copy()
pairs["rows"] = [len(hist[(s, o)][0]) for s, o in zip(pairs.series_id, pairs.origin_day)]
pairs["tier"] = [tier_at(s, o) for s, o in zip(pairs.series_id, pairs.origin_day)]
pairs["in37"] = pairs.series_id.isin(HEAD)
pairs["cls"] = pairs.series_id.map(lambda x: meta.get(x, {}).get("instrument_class", ""))
pairs["bucket"] = pd.cut(pairs["rows"], [0, 29, 59, 89, 10**6], labels=["<30", "30-59", "60-89", "90+"]).astype(str)
for k in C:
    C[k] = C[k].merge(pairs, on=["series_id", "origin_day"], how="inner")
sk = lambda c: float(1 - c.loss.sum() / c.baseline_loss.sum()) if len(c) and c.baseline_loss.sum() > 0 else float("nan")
cov = lambda c: float(((c.y >= c.q10) & (c.y <= c.q90)).mean()) if len(c) else float("nan")
ORDER = ["drift", "mix", "final", "orch5"] + [m for m in MEMBERS if m != "mix"]
res = {}


def table(title, masks):
    print(f"\n## {title}")
    print(f"{'slice':<28}{'cells':>7}{'series':>7}{'origins':>8}  " + "".join(f"{k:>10}" for k in ORDER) +
          f"{'final-drift':>13}{'cov final':>10}{'cov drift':>10}")
    for lab, fn in masks:
        x = {k: C[k][fn(C[k])] for k in ORDER}
        n = len(x["final"])
        if not n:
            continue
        r = {k: sk(x[k]) for k in ORDER}
        res[f"{title} | {lab}"] = {"cells": n, **r, "cov_final": cov(x["final"]), "cov_drift": cov(x["drift"]),
                                   "baseline_loss": float(x["final"].baseline_loss.sum())}
        print(f"{lab:<28}{n:>7}{x['final'].series_id.nunique():>7}{x['final'].origin_day.nunique():>8}  " +
              "".join(f"{r[k]:>+10.4f}" for k in ORDER) +
              f"{r['final'] - r['drift']:>+13.4f}{cov(x['final']):>10.2f}{cov(x['drift']):>10.2f}", flush=True)


B = ["<30", "30-59", "60-89", "90+"]
table("universe", [("fixed 37", lambda c: c.in37), ("tier at origin", lambda c: c.tier),
                   ("fixed 37, not yet in tier", lambda c: c.in37 & ~c.tier), ("all rental", lambda c: c.in37 | ~c.in37),
                   ("not in the 37", lambda c: ~c.in37)])
table("fixed 37 by rows at origin", [(b, lambda c, b=b: c.in37 & (c.bucket == b)) for b in B])
table("all rental by rows at origin", [(b, lambda c, b=b: (c.bucket == b)) for b in B])
table("all rental, 60+ rows, by class", [(cl, lambda c, cl=cl: (c.rows >= 60) & (c.cls == cl)) for cl in sorted(pairs.cls.unique())])
table("fixed 37 by collector", [(src, lambda c, src=src: c.in37 & c.series_id.str.startswith(src))
                                for src in ["fastgpu", "gpurentalprices", "afhubbard"]])
table("fixed 37 by horizon", [(f"h={h}", lambda c, h=h: c.in37 & (c.horizon_days == h)) for h in H])
table("tier at origin by horizon", [(f"h={h}", lambda c, h=h: c.tier & (c.horizon_days == h)) for h in H])
LATE = splits.origins("dev")[-14:]
table("last 14 dev origins", [("fixed 37", lambda c: c.in37 & c.origin_day.isin(LATE)),
                              ("tier at origin", lambda c: c.tier & c.origin_day.isin(LATE)),
                              ("fixed 37, 30+ rows", lambda c: c.in37 & (c.rows >= 30) & c.origin_day.isin(LATE))])
(OUT / "diag.json").write_text(json.dumps(res, indent=1))
print(f"\n# total {time.time() - t0:.0f}s")
