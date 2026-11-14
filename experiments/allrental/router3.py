"""Fixed forecaster + activity gate with a history-span condition (a series is gated only if it has n days of history
with fewer than m changes). Selection on early origins (head-early must not drop below mix), report on late."""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, "experiments/allrental")
import router as R
from router2 import ens, E
from gpuf import compare

od = R.base.origin_day.to_numpy()
SPAN = np.zeros(len(R.base), int)
for sid, idx in R.base.groupby("series_id").indices.items():
    d, _ = R.store.arrays(sid)
    SPAN[idx] = od[idx] - d[0]
H = R.base["head"].to_numpy()
FC = ["mix@1.0", "mix_cls@1.0", "ens_3mix@1.0", "ens_mctg@1.0", "ens_3mix_ct@1.0", "ens_mct@1.0"]
GRID = [(n, m) for n in (14, 30, 60) for m in (1, 2, 3)]
rows, cand = [], []
mix_he = R.skill(R.L["mix@1.0"], R.early & H)
for k in FC:
    rows.append(R.report(k, R.L[k]))
    for n, m in GRID:
        gated = (R.ACT[n] < m) & (SPAN >= n)
        l = np.where(gated, R.B, R.L[k])
        r = R.report(f"  {k} gate n{n} m{m}", l); r["gated_frac"] = round(gated.mean(), 3)
        rows.append(r)
        cand.append((R.skill(l, R.early), R.skill(l, R.early & H) >= mix_he - 0.002, k, n, m))
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
print(pd.DataFrame(rows).to_string(index=False))
ok = [c for c in cand if c[1]]
best = max(ok, key=lambda c: c[0])
print("selected on early (head-early >= mix - 0.002):", best)
best_any = max(cand, key=lambda c: c[0]); print("unconstrained early best:", best_any)
json.dump({"forecaster": best[2], "n": best[3], "m": best[4]}, open("runs/allrental/selected.json", "w"))
