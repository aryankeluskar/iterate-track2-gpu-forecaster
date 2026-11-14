import numpy as np, pandas as pd, datetime as dt
from gpuf import compare
import report as R
pd.set_option("display.width", 250)
drift, mix = R.load("drift"), R.load("mix")
best = ["mid7_n80", "mid7_n150", "mid14_n150", "mid7_n80_tail", "mid7"]
C = {n: R.load(n) for n in best}
print(pd.DataFrame([R.row(n, c, drift, mix) for n, c in {**C, **{f"blend(mix,{n})": R.blend(mix, C[n]) for n in best}}.items()]).round(4).drop(columns="q50_ratio").to_string(index=False))
n = "mid7_n80"; mid = C[n]; bl = R.blend(mix, mid)
q50l = lambda c: 0.5 * (c.y - c.q50).abs()
for nm, c in [("mix", mix), (n, mid), ("blend", bl), ("drift", drift)]:
    print("q50 loss / last-value q50 loss:", nm, round(q50l(c).sum() / (0.5 * (c.y - c.baseline).abs()).sum(), 4))
T = dt.date(2026, 9, 11).toordinal()
for lab, f in [("first half (origins<=09-11)", lambda c: c[c.origin_day <= T]), ("second half", lambda c: c[c.origin_day > T])]:
    print(lab, {nm: round(R.skill(f(c)), 4) for nm, c in [("drift", drift), ("mix", mix), (n, mid), ("blend", bl)]})
r = np.log(drift.y / drift.baseline)
kind = pd.Series(np.select([r == 0, r.abs() < .01, r.abs() < .05, r > 0], ["0 none", "1 <1%", "2 1-5%", "3 up>5%"], "4 down>5%"), index=drift.index)
T0 = drift.baseline_loss.sum()
def split(col):
    out = {}
    for nm, c in [("mix", mix), (n, mid), ("blend", bl)]:
        g = c.groupby(col if not isinstance(col, pd.Series) else col.values)
        out[nm] = (drift.groupby(col if not isinstance(col, pd.Series) else col.values).loss.sum() - g.loss.sum()) / T0
    return pd.DataFrame(out)
print("\nskill gain over drift, share of total base loss, by collector:\n", split("source_id").round(4))
print("by horizon:\n", split("horizon_days").round(4))
print("by outcome:\n", split(kind).round(4))
for nm, c in [("mix", mix), (n, mid)]:
    print("coverage by horizon (below q10, above q90)", nm, {h: (round((g.y < g.q10).mean(), 3), round((g.y > g.q90).mean(), 3)) for h, g in c.groupby("horizon_days")})
