"""Dev-period only (rows <= 2026-10-13). Are the big moves that carry the loss predictable?
1 clustering in time, 2 reversal after a jump, 3 cross-collector lead-lag for the same GPU, 4 weekday."""
import numpy as np, pandas as pd
from gpuf import data
pd.set_option("display.width", 250)
END = "2026-10-13"; START = "2026-07-01"
cat = data.load_catalog(); sids = data.universe("rental_headline", None)
df = pd.read_csv("runs/series/series_daily.csv"); dcol = [c for c in df.columns if "date" in c][0]; vcol = [c for c in df.columns if c in ("value", "price", "y", "usd_per_gpu_hour")][0]
df = df[df.series_id.isin(sids) & (df[dcol] <= END) & (df[dcol] >= START)]
P = df.pivot(index=dcol, columns="series_id", values=vcol); P.index = pd.to_datetime(P.index); P = P.asfreq("D")
L = np.log(P); r1 = L.diff()            # 1-day log change, NaN across gaps
meta = cat.set_index("series_id").loc[P.columns, ["source_id", "instrument_class", "gpu_model"]]
big = r1.abs() > 0.05
print("series", P.shape[1], "days", P.shape[0], "| obs", int(r1.notna().sum().sum()), "| changed", round(float((r1 != 0).where(r1.notna()).mean().mean()), 3), "| big(>5%)", int(big.sum().sum()))
# 1 clustering
n_big = big.sum(axis=1); n_obs = r1.notna().sum(axis=1)
print("\n1. days with >=1 big move:", int((n_big > 0).sum()), "of", int((n_obs > 0).sum()), "| share of big moves on the 5 busiest days:", round(n_big.sort_values().tail(5).sum() / n_big.sum(), 3))
print(n_big.sort_values().tail(8).to_string())
for src in meta.source_id.unique():
    c = meta.index[meta.source_id == src]; b = big[c]; a = (r1[c] != 0).where(r1[c].notna())
    frac = a.mean(axis=1)   # share of the collector's series that changed that day
    # does today's breadth of change predict tomorrow's big-move rate?
    tom = b.shift(-1).where(r1[c].shift(-1).notna()).mean(axis=1)
    hi = frac > frac.median()
    print(f"   {src}: next-day big-move rate after a busy day {tom[hi].mean():.4f} vs quiet day {tom[~hi].mean():.4f}; lag-1 autocorr of daily breadth {frac.autocorr(1):.2f}")
# 2 reversal: after a big move of size x, what is the change over the next h days?
print("\n2. after a 1-day move >5%: later change as a fraction of the jump (negative = reverts)")
for h in (1, 3, 7):
    fut = L.shift(-h) - L
    m = big & fut.notna()
    x = r1.where(m).stack(); y = fut.where(m).stack()
    beta = float((x * y).sum() / (x * x).sum())
    print(f"   h={h}: n={len(x)} slope={beta:+.3f} | share fully or more than half reverted={float(((y / x) < -0.5).mean()):.3f} | share unchanged after={float((y == 0).mean()):.3f}")
    for src in meta.source_id.unique():
        c = meta.index[meta.source_id == src]; xs = r1[c].where(m[c]).stack(); ys = fut[c].where(m[c]).stack()
        if len(xs) > 5: print(f"        {src}: n={len(xs)} slope={float((xs*ys).sum()/(xs*xs).sum()):+.3f}")
# same for smaller moves
m = (r1.abs() > 0.01) & (r1.abs() <= 0.05)
for h in (1, 3, 7):
    fut = L.shift(-h) - L; mm = m & fut.notna(); x = r1.where(mm).stack(); y = fut.where(mm).stack()
    print(f"   moves 1-5%, h={h}: n={len(x)} slope={float((x*y).sum()/(x*x).sum()):+.3f}")
# 3 cross-collector lead-lag for the same gpu and class
print("\n3. same GPU and class on two collectors: corr of A's change on day t with B's change on day t+k")
rows = []
for (g, ic), grp in meta.groupby(["gpu_model", "instrument_class"]):
    if grp.source_id.nunique() < 2: continue
    ids = list(grp.index)
    for a in ids:
        for b_ in ids:
            if a == b_ or meta.source_id[a] == meta.source_id[b_]: continue
            for k in (-1, 0, 1, 2, 3):
                z = pd.concat([r1[a], r1[b_].shift(-k)], axis=1).dropna()
                if len(z) > 20 and z.std().min() > 0: rows.append((meta.source_id[a], meta.source_id[b_], g, k, z.corr().iloc[0, 1], len(z)))
ll = pd.DataFrame(rows, columns=["A", "B", "gpu", "k", "corr", "n"])
if len(ll): print(ll.groupby(["A", "B", "k"])["corr"].agg(["mean", "median", "count"]).round(3).to_string())
lv = []
for (g, ic), grp in meta.groupby(["gpu_model", "instrument_class"]):
    if grp.source_id.nunique() < 2: continue
    ids = list(grp.index)
    for i, a in enumerate(ids):
        for b_ in ids[i + 1:]:
            gap = (L[a] - L[b_]).dropna()
            if len(gap) > 20: lv.append((a.split(".")[0], b_.split(".")[0], g, ic, gap.mean(), gap.std(), gap.autocorr(1), len(gap)))
print("\n   level gap between collectors for the same GPU (log): ")
print(pd.DataFrame(lv, columns=["A", "B", "gpu", "class", "mean_gap", "sd_gap", "ac1", "n"]).round(3).to_string(index=False))
# 4 weekday
wd = pd.DataFrame({"changed": (r1 != 0).where(r1.notna()).groupby(P.index.dayofweek).mean().mean(axis=1), "big": big.where(r1.notna()).groupby(P.index.dayofweek).mean().mean(axis=1), "absmove": r1.abs().groupby(P.index.dayofweek).mean().mean(axis=1)})
wd.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]; print("\n4. by weekday of the change:"); print(wd.round(4).to_string())
