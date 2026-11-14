"""Descriptive transition rates per (collector, class), rows dated <= 2026-10-06 (last dev origin)."""
import numpy as np, pandas as pd
from gpuf import panel
from gpuf.data import starter_common as sc
CUT = sc.day_of(sc.parse_date("2026-10-06"))
df = panel.load(); df = df[(df.day <= CUT) & df.cls.isin(["neocloud_rate_card", "neocloud_spot", "hyperscaler_spot", "marketplace_ask"])]
rows = []
for (src, cls), g in df.groupby(["src", "cls"]):
    st = dict(n_present=0, stay=0, reprice=0, exit=0, absent_recent=0, ret=0, entries=0, panel_days=0, rp_same_provider_day=0)
    for k, p in g.groupby(["gpu", "tier"]):
        days = np.sort(p.day.unique()); piv = p.pivot_table(index="day", columns="key", values="price", aggfunc="first").reindex(days)
        seen = piv.notna().to_numpy(); pr = piv.to_numpy(); provs = p.drop_duplicates("key").set_index("key").provider.reindex(piv.columns).to_numpy()
        ever = np.zeros(seen.shape[1], bool); lastseen = np.full(seen.shape[1], -10**9)
        for t in range(len(days) - 1):
            if days[t + 1] - days[t] != 1:
                ever |= seen[t]; lastseen[seen[t]] = days[t]; continue
            ever |= seen[t]; lastseen[seen[t]] = days[t]
            a, b = seen[t], seen[t + 1]
            st["panel_days"] += 1
            st["n_present"] += a.sum(); st["exit"] += (a & ~b).sum()
            both = a & b; rp = both & ~np.isclose(pr[t], pr[t + 1])
            st["reprice"] += rp.sum(); st["stay"] += (both & ~rp).sum()
            rec = ~a & ever & (days[t] - lastseen <= 7)
            st["absent_recent"] += rec.sum(); st["ret"] += (rec & b).sum()
            st["entries"] += (b & ~ever).sum()
            if rp.sum() >= 2:
                pv = pd.Series(provs[rp]).value_counts(); st["rp_same_provider_day"] += int(pv[pv >= 2].sum())
    n = st["n_present"]
    rows.append(dict(src=src, cls=cls, panel_days=st["panel_days"], offers_per_day=round(n / max(st["panel_days"], 1), 1),
                     p_reprice=round(st["reprice"] / n, 4), p_exit=round(st["exit"] / n, 4),
                     p_return=round(st["ret"] / max(st["absent_recent"], 1), 3), entries_per_day=round(st["entries"] / st["panel_days"], 3),
                     share_reprices_with_same_provider=round(st["rp_same_provider_day"] / max(st["reprice"], 1), 2)))
print(pd.DataFrame(rows).to_string())
