"""Diagnose h=7 cells with |move| > 5% (dev cells, truths <= 2026-10-13): what changed in the panel between origin
and target, and where v1 put q90. Also: are reprices within a panel-day clustered beyond independence?"""
import numpy as np, pandas as pd
from gpuf import panel
from gpuf.methods.panel import _pivot
c = pd.read_parquet("runs/panel/v1.parquet")
c = c[(c.horizon_days == 7) & c.series_id.map(panel.supported)]
r = np.log(c.y / c.baseline); big = c[r.abs() > 0.05].copy()
rows = []
for _, x in big.iterrows():
    o = panel.offers(x.series_id, int(x.target_day))
    days, keys, M = _pivot(o)
    i0, i1 = np.searchsorted(days, x.origin_day), np.searchsorted(days, x.target_day)
    a, b = M[i0], M[i1]; sa, sb = ~np.isnan(a), ~np.isnan(b)
    rep = sa & sb & ~np.isclose(np.nan_to_num(a), np.nan_to_num(b))
    rows.append(dict(sid=x.series_id.split(".", 1)[1][:34], up=x.y > x.baseline, n0=int(sa.sum()), n_rep=int(rep.sum()),
                     n_exit=int((sa & ~sb).sum()), n_enter=int((~sa & sb).sum()),
                     rep_same_sign=int(rep.sum() >= 2 and abs(np.sign(np.log(b[rep] / a[rep])).sum()) == rep.sum()),
                     above_q90=x.y > x.q90, move=round(float(np.log(x.y / x.baseline)), 3), q90_off=round(float(np.log(x.q90 / x.baseline)), 3)))
d = pd.DataFrame(rows)
print(d.groupby("up")[["n0", "n_rep", "n_exit", "n_enter", "rep_same_sign", "above_q90"]].mean().round(2))
print("cells", len(d), "with an entrant", (d.n_enter > 0).mean().round(2), "with >=2 reprices", (d.n_rep >= 2).mean().round(2))
print(d[d.up].sort_values("move").tail(25).to_string())
# reprice clustering: per panel-day, count of repricing offers vs binomial expectation from the same day's present offers
from gpuf.data import starter_common as sc
CUT = sc.day_of(sc.parse_date("2026-10-06"))
obs, exp2 = 0, 0.0; k_ge2 = 0; n_days_rep = 0
for key in panel._index():
    if key[1] not in ("neocloud_rate_card", "neocloud_spot", "marketplace_ask"): continue
    days, keys, M = _pivot(panel.panel_offers(key, CUT))
    for t in range(1, len(days)):
        if days[t] - days[t - 1] != 1: continue
        both = ~np.isnan(M[t]) & ~np.isnan(M[t - 1]); rp = both & ~np.isclose(np.nan_to_num(M[t]), np.nan_to_num(M[t - 1]))
        if rp.any(): n_days_rep += 1; k_ge2 += rp.sum() >= 2
print("panel-days with a reprice", n_days_rep, "share with >=2 offers repricing", round(k_ge2 / max(n_days_rep, 1), 3))
