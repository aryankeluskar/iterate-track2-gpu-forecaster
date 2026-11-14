"""Does a provider reprice its whole card with one policy? Same-day co-movement of a provider's offers across GPUs.
Rows <= 2026-10-13 only."""
import datetime as dt
import numpy as np, pandas as pd
from gpuf import panel
CUT = dt.date(2026, 10, 13).toordinal()
df = panel.load(); df = df[df.day <= CUT].sort_values(["src", "cls", "gpu", "tier", "key", "day"])
g = df.groupby(["src", "cls", "gpu", "tier", "key"])
df["pd"] = g["day"].shift(1); df["pp"] = g["price"].shift(1)
c = df[df.day - df.pd == 1].copy(); c["r"] = np.log(c.price / c.pp); c["ch"] = c.r != 0
for src, prov in [("fastgpu_daily", "verda"), ("gpurentalprices", "verda"), ("gpurentalprices", "scaleway"),
                  ("fastgpu_daily", "spheron"), ("gpurentalprices", "sfcompute"), ("fastgpu_daily", "sfcompute")]:
    x = c[(c.src == src) & (c.provider == prov)]
    if x.empty: continue
    x = x.assign(card=x.gpu + "/" + x.tier + "/" + x.cls)
    P = x.groupby(["day", "card"]).r.mean().unstack()   # day x card mean log change
    C = (P != 0).where(P.notna())
    days_any = (C.sum(1) > 0)
    # on days where >=1 card repriced, share of observed cards that repriced
    share = (C[days_any].sum(1) / C[days_any].notna().sum(1))
    # cross-card correlation of daily changes (pairs with >=10 common days)
    cors = []
    cols = list(P.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = P[cols[i]], P[cols[j]]; m = a.notna() & b.notna()
            if m.sum() >= 10 and a[m].std() > 0 and b[m].std() > 0: cors.append(np.corrcoef(a[m], b[m])[0, 1])
    # dispersion of same-day nonzero sizes across cards
    nz = P.where(P != 0)
    disp = (nz.std(1) / nz.abs().mean(1)).dropna()
    print(f"{src:16s} {prov:10s} cards={P.shape[1]:2d} days={len(P)} reprice-days={int(days_any.sum())} "
          f"share_of_cards_moving_on_reprice_days: median={share.median():.2f} mean={share.mean():.2f} | "
          f"pairwise corr of daily change median={np.median(cors) if cors else np.nan:.2f} (n_pairs={len(cors)}) | "
          f"same-day size CV across cards median={disp.median():.2f}")
    # verda weekly mean by card
    if prov == "verda":
        wk = ((P.index - P.index.min()) // 7)
        print("   weekly mean daily log change (%) by card (first 6 cards):")
        print((P.groupby(wk).mean() * 100).iloc[:, :6].round(2).to_string())
