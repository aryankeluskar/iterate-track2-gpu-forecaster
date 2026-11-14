import numpy as np, pandas as pd, datetime as dt, sys
from gpuf import panel
CUT = dt.date(2026,10,13).toordinal()
df = panel.load(); df = df[df.day <= CUT].copy()
head = df.sort_values(["src","cls","gpu","tier","key","day"])
g = head.groupby(["src","cls","gpu","tier","key"])
head["pd"] = g["day"].shift(1); head["pp"] = g["price"].shift(1)
c = head[head.day - head.pd == 1].copy(); c["r"] = np.log(c.price/c.pp); c["ch"] = c.r != 0
od = df.groupby(["src","cls","provider"]).agg(offer_rows=("price","size"), offer_days=("day","nunique"), first_day=("day","min"), last_day=("day","max")).reset_index()
pv = c.groupby(["src","cls","provider"]).agg(pairs=("ch","size"), n_rep=("ch","sum"), p_rep=("ch","mean"),
    n_up=("r", lambda x: (x>0).sum()), n_down=("r", lambda x: (x<0).sum())).reset_index()
pv["up_share"] = pv.n_up / pv.n_rep.where(pv.n_rep>0)
out = od.merge(pv, on=["src","cls","provider"], how="left")
for k in ("first_day","last_day"): out[k] = out[k].map(lambda d: dt.date.fromordinal(int(d)).isoformat())
out.to_csv("experiments/policy/results/measured_rates.csv", index=False)
print(out.groupby("provider").agg(rows=("offer_rows","sum"), src=("src", lambda s: ",".join(sorted(set(s)))), cls=("cls", lambda s: ",".join(sorted(set(s))))).to_string())
