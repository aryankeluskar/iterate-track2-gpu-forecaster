"""Audit item 2: the headline universe chosen as of 2026-11-06 against the headline tier computed at each origin.

Starter rule (starter/build_series.py build_catalog, defaults): a daily_statistics series is headline at as_of d if
it has >= 60 rows on or before d, its last row is within 3 days of d, it took >= 5 distinct values (rounded 1e-6)
in (d-90, d], and the median n_providers over rows <= d is >= 3. Dev split only.
Usage: PYTHONPATH=src .venv/bin/python experiments/audit/universe.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf import data, harness, methods, splits

OUT = Path(__file__).resolve().parent / "results"
S = pd.read_csv(data.series_path(), dtype={"series_id": str}, low_memory=False)
cat = data.load_catalog()
ds_ids = set(cat.loc[cat["table"] == "daily_statistics", "series_id"])
S = S[S["series_id"].isin(ds_ids)].dropna(subset=["value"]).copy()
S["day"] = pd.to_datetime(S["date"]).map(pd.Timestamp.toordinal).astype(np.int64)
G = {s: g.sort_values("day") for s, g in S.groupby("series_id")}
HEAD37 = data.universe("rental_headline")


def headline_at(d):
    out = []
    for s, g in G.items():
        h = g[g["day"] <= d]
        if len(h) < 60 or d - int(h["day"].iloc[-1]) > 3:
            continue
        if h.loc[h["day"] > d - 90, "value"].round(6).nunique() < 5:
            continue
        p = pd.to_numeric(h["n_providers"], errors="coerce").dropna()
        if not len(p) or p.median() < 3:
            continue
        out.append(s)
    return set(out)


check = headline_at(splits.TEST[0])
pit = {o: headline_at(o) for o in splits.DEV}
MIX = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
res = {"rule_reproduces_catalog_at_2026-11-06": sorted(check) == sorted(HEAD37), "n_at_2026-11-06": len(check),
       "per_origin": {}, "scores": {}}
for o in splits.DEV[::7]:
    pi = pit[o]
    res["per_origin"][pd.Timestamp.fromordinal(o).date().isoformat()] = {
        "n_pit": len(pi), "n_pit_and_37": len(pi & set(HEAD37)), "n_pit_not_37": len(pi - set(HEAD37)),
        "n_37_not_pit": len(set(HEAD37) - pi)}
cells = {}
for name, (m, p) in {"drift": ("drift", {}), "mix": ("mix", MIX)}.items():
    c = harness.evaluate(methods.get(m, **p), "dev", "rental_all", name=m, params=p).cells
    cells[name] = c
    keep = np.array([s in pit[o] for s, o in zip(c["series_id"], c["origin_day"])])
    in37 = c["series_id"].isin(HEAD37).to_numpy()
    sk = lambda x: float(1 - x["loss"].sum() / x["baseline_loss"].sum())
    res["scores"][name] = {"headline37_fixed": sk(c[in37]), "n37": int(in37.sum()),
                           "headline_point_in_time": sk(c[keep]), "n_pit": int(keep.sum()),
                           "pit_and_37": sk(c[keep & in37]), "pit_not_37": sk(c[keep & ~in37]) if (keep & ~in37).any() else None,
                           "n_pit_not_37": int((keep & ~in37).sum()), "rental_all": sk(c)}
for k in ("headline37_fixed", "headline_point_in_time"):
    res["scores"][f"mix_minus_drift_{k}"] = res["scores"]["mix"][k] - res["scores"]["drift"][k]
print(json.dumps(res, indent=1))
(OUT / "universe.json").write_text(json.dumps(res, indent=1))
