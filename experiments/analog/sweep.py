"""Dev-only sweep of analog variants. Usage: sweep.py STAGE"""
import json, sys, time
import numpy as np, pandas as pd
from gpuf import harness, methods, compare
U = "rental_headline"
MIX = ("mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30})
_cache = {}

def cells(m, p):
    key = json.dumps([m, p], sort_keys=True)
    if key not in _cache:
        _cache[key] = harness.evaluate(methods.get(m, **p), "dev", U, name=m, params=p).cells
    return _cache[key]

def line(label, m, p, extra=""):
    c = cells(m, p); d = cells("drift", {}); x = cells(*MIX)
    sk = 1 - c.loss.sum() / c.baseline_loss.sum()
    a = compare.paired(c, d); b = compare.paired(c, x)
    cov = ((c.y >= c.q10) & (c.y <= c.q90)).mean()
    print(f"{label:46s} skill {sk:+.4f}  vsDrift {a['d_pooled_skill']:+.4f} [{a['ci90_d_pooled_skill'][0]:+.3f},{a['ci90_d_pooled_skill'][1]:+.3f}]  "
          f"vsMix {b['d_pooled_skill']:+.4f} [{b['ci90_d_pooled_skill'][0]:+.3f},{b['ci90_d_pooled_skill'][1]:+.3f}] cov {cov:.2f} {extra}", flush=True)
    return sk

def A(**p): return ("analog", p)
if __name__ == "__main__":
    stage = sys.argv[1]
    t0 = time.time()
    if stage == "base":
        line("drift", "drift", {}); line("mix", *MIX)
        for pool in ("self", "cc", "class", "all"):
            for k in (30, 100, 300):
                for ce in ("median", "last"):
                    line(f"{pool} k={k} centre={ce}", *A(pool=pool, k=k, centre=ce))
    if stage == "refine":
        for pool in ("cc", "all"):
            for k in (300, 600, 1500):
                line(f"{pool} k={k}", *A(pool=pool, k=k))
            line(f"{pool} k=300 uniform", *A(pool=pool, k=300, kern="uniform"))
            line(f"{pool} k=300 hl=30", *A(pool=pool, k=300, hl=30))
            line(f"{pool} k=300 rescale", *A(pool=pool, k=300, rescale=True))
            line(f"{pool} k=300 scale=1.2", *A(pool=pool, k=300, scale=1.2))
            line(f"{pool} k=300 scale=0.8", *A(pool=pool, k=300, scale=0.8))
            line(f"{pool} k=300 centre=0.5", *A(pool=pool, k=300, centre=0.5))
    if stage == "abl":
        for pool in ("cc", "all"):
            line(f"{pool} k=600 full", *A(pool=pool, k=600))
            for g in ("since", "n7", "n14", "mad7", "mad30", "size", "sign", "nprov", "pos"):
                line(f"{pool} k=600 drop {g}", *A(pool=pool, k=600, drop=[g]))
            line(f"{pool} k=600 no state (all off)", *A(pool=pool, k=600, drop=list(["since","n7","n14","mad7","mad30","size","sign","nprov","pos"])))
    if stage == "borrow":
        for pool, ex in (("cc", ()), ("class", ()), ("all", ()), ("all", ("afhubbard",)), ("all", ("fastgpu_daily","gpurentalprices")),
                         ("class", ("afhubbard",)), ("all", ("afhubbard","tanod")), ("all", ("tanod",))):
            line(f"{pool} excl={ex} k=600", *A(pool=pool, k=600, excl=list(ex)))
    print("time", round(time.time() - t0, 1))
