"""Dev report for `fragility`: against base mix and drift, by cause, per-tail coverage, halves, blend with mix."""
import datetime as dt
import json
import sys
import numpy as np
import pandas as pd
from gpuf import compare, harness, methods
from gpuf.data import starter_common

K = ["series_id", "origin_day", "horizon_days"]
cells = pd.read_parquet("experiments/autopsy/results/hday_cells_dev.parquet")[K + ["cause"]]
HALF = starter_common.day_of(dt.date(2026, 9, 11))
CFG = json.load(open(sys.argv[1]))
cache = {}


def ev(name, params):
    key = json.dumps([name, params], sort_keys=True)
    if key not in cache:
        cache[key] = harness.evaluate(methods.get(name, **params), "dev", "rental_headline", name=name, params=params).cells
    return cache[key]


base = ev("fragility", {"mode": "off"})
drift = ev("drift", {})
mixref = ev("mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30})
B = base.baseline_loss.sum()
out = {}
for label, (name, params) in CFG.items():
    c = ev(name, params)
    m = c.merge(cells, on=K, how="left")
    mb = base.merge(cells, on=K, how="left")
    r = {"skill": round(1 - c.loss.sum() / B, 4), "cov": round(float(((c.y >= c.q10) & (c.y <= c.q90)).mean()), 3)}
    for ref_name, ref in (("base", base), ("drift", drift)):
        p = compare.paired(c, ref)
        r[f"d_{ref_name}"] = [round(p["d_pooled_skill"], 4), [round(x, 4) for x in p["ci90_d_pooled_skill"]]]
    r["d_vs_mix_ref_halves"] = {}
    for hn, sel in (("<=09-11", lambda x: x.origin_day <= HALF), (">09-11", lambda x: x.origin_day > HALF)):
        a, b = c[sel(c)], base[sel(base)]
        r["d_vs_mix_ref_halves"][hn] = round(float((b.loss.sum() - a.loss.sum()) / b.baseline_loss.sum()), 4)
    r["by_cause"] = {}
    for cz, g in m.groupby("cause"):
        gb = mb[mb.cause == cz]
        r["by_cause"][cz] = dict(n=len(g), loss_ratio_to_last=round(float(g.loss.sum() / max(g.baseline_loss.sum(), 1e-12)), 3),
                                 base_ratio=round(float(gb.loss.sum() / max(gb.baseline_loss.sum(), 1e-12)), 3),
                                 d_skill_pts=round(float((gb.loss.sum() - g.loss.sum()) / B), 4))
    r["tail_cov"] = {}
    for h, g in c.groupby("horizon_days"):
        r["tail_cov"][int(h)] = dict(below_q10=round(float((g.y < g.q10).mean()), 3), above_q90=round(float((g.y > g.q90).mean()), 3))
    out[label] = r
    print(label, json.dumps(r), flush=True)
json.dump(out, open("experiments/fragility/results/" + sys.argv[2], "w"), indent=1)
