import numpy as np, pandas as pd
from gpuf import harness, methods, compare
U = "rental_headline"
MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
ENS3 = ["ens", {"members": [["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}], ["mix", {"pool": "cc", "k": 20, "state": "dirk", "sk": 7, "hl": 30}], ["mix", {"pool": "all", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]]}]
V = {"conf_all": dict(mode="conf", pool="all"), "conf_all_ew_pw1": dict(mode="conf", pool="all", hl=30, pw=1),
     "aci_slow": dict(mode="aci", pool="all", gamma=0.003, min_a=0.05, max_a=0.2)}
for bn, b in (("mix", MIX), ("ens3", ENS3)):
    bc = harness.evaluate(methods.get(b[0], **b[1]), "dev", U, name="b").cells
    od = np.sort(bc.origin_day.unique()); mid = od[len(od) // 2]
    for vn, vp in V.items():
        c = harness.evaluate(methods.get("tail", base=b, **vp), "dev", U, name="t").cells
        for nm, m in (("first half", bc.origin_day < mid), ("second half", bc.origin_day >= mid)):
            T = bc.baseline_loss[m].sum()
            fl = (bc.y == bc.baseline) & m
            print(f"{bn:5s} {vn:16s} {nm:11s} base skill {1 - bc.loss[m].sum() / T:.4f} tail skill {1 - c.loss[m].sum() / T:.4f} d {(bc.loss[m].sum() - c.loss[m].sum()) / T:+.4f}"
                  f" | no-change cells cost {(bc.loss[fl].sum() - c.loss[fl].sum()) / T:+.4f}  moving cells {(bc.loss[m & ~fl].sum() - c.loss[m & ~fl].sum()) / T:+.4f}")
