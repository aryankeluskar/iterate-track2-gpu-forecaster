"""Per headline series (rows <= 2026-10-06): panel size and what caused each 1-day median change
(composition only / reprice only / both), plus loss-relevant share by |log change|."""
import numpy as np, pandas as pd
from gpuf import data, panel
from gpuf.data import starter_common as sc
CUT = sc.day_of(sc.parse_date("2026-10-06"))
out = []; agg = {"comp": 0.0, "rep": 0.0, "both": 0.0}; cnt = {"comp": 0, "rep": 0, "both": 0}
for sid in data.universe("rental_headline"):
    if not panel.supported(sid): continue
    o = panel.offers(sid, CUT); days = np.sort(o.day.unique())
    piv = o.pivot_table(index="day", columns="key", values="price", aggfunc="first").reindex(days)
    pr = piv.to_numpy(); seen = ~np.isnan(pr); med = np.nanmedian(pr, axis=1)
    n_rep = n_comp = 0; c = {"comp": 0, "rep": 0, "both": 0}
    for t in range(len(days) - 1):
        if days[t + 1] - days[t] != 1 or np.isclose(med[t], med[t + 1]): continue
        comp = (seen[t] != seen[t + 1]).any(); rep = (seen[t] & seen[t + 1] & ~np.isclose(np.nan_to_num(pr[t]), np.nan_to_num(pr[t + 1]))).any()
        k = "both" if comp and rep else "comp" if comp else "rep"
        c[k] += 1; agg[k] += abs(np.log(med[t + 1] / med[t])); cnt[k] += 1
    out.append(dict(sid=sid.split(".", 1)[1][:45], src=sid.split(".")[0][:4], n_offers=round(seen.sum(1).mean(), 1),
                    n_keys=pr.shape[1], days=len(days), **c))
print(pd.DataFrame(out).to_string())
print("count of median changes by cause", cnt)
print("sum |log change| by cause", {k: round(v, 3) for k, v in agg.items()})
