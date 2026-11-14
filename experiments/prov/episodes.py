"""Robustness: (1) episodes where a dynamic provider's trailing drift changed sign, error of prov vs mix around them;
(2) adaptation to a regime start (verda on gpurentalprices, static then trending). Rows <= 2026-10-13 only."""
import datetime as dt, json
import numpy as np, pandas as pd
from gpuf import panel
from gpuf.data import starter_common
CUT = dt.date(2026, 10, 13).toordinal()
iso = starter_common.iso
df = panel.load(); df = df[df.day <= CUT].sort_values(["src", "cls", "gpu", "tier", "key", "day"])
g = df.groupby(["src", "cls", "gpu", "tier", "key"])
df["pd"] = g["day"].shift(1); df["pp"] = g["price"].shift(1)
c = df[df.day - df.pd == 1].copy(); c["r"] = np.log(c.price / c.pp)
pdm = c.groupby(["src", "provider", "day"]).agg(r=("r", "mean"), k=("r", lambda x: (x != 0).mean())).reset_index()
mix = pd.read_parquet("runs/panel/mix.parquet")
runs = {n: pd.read_parquet(f"runs/prov/{n}.parquet") for n in ("L1_W7", "L1", "L1_W21", "L1_W21_gdyn")}
K = ["series_id", "origin_day", "horizon_days"]
sid_provs = {}
for sid in mix.series_id.unique():
    if panel.supported(sid):
        sid_provs[sid] = set(panel.offers(sid, CUT).provider)
print("== drift sign changes (7-day trailing mean daily log change, provider reprice rate > 15%, |drift| > 0.1%/day both sides)")
eps = []
for (src, pv), x in pdm.groupby(["src", "provider"]):
    x = x.set_index("day").sort_index()
    m7 = x.r.rolling(7, min_periods=5).mean(); k7 = x.k.rolling(7, min_periods=5).mean()
    s = np.sign(m7.where((m7.abs() > 0.001) & (k7 > 0.15)))
    s = s.dropna()
    flips = s.index[1:][(s.values[1:] != s.values[:-1])]
    for d in flips:
        eps.append((src, pv, int(d), float(m7.loc[:d].iloc[-8]) if len(m7.loc[:d]) > 8 else np.nan, float(m7.get(d + 7, np.nan))))
for src, pv, d, before, after in eps:
    sids = [s for s, ps in sid_provs.items() if s.startswith(src) and pv in ps]
    line = f"{src} {pv} flip on {iso(d)} drift7 before {before*100:+.2f}%/d after(+7d) {after*100:+.2f}%/d, {len(sids)} series"
    for win, lo, hi in (("pre[-7,0)", d - 7, d), ("post[0,+7)", d, d + 7), ("post[+7,+14)", d + 7, d + 14)):
        mm = mix[mix.series_id.isin(sids) & (mix.origin_day >= lo) & (mix.origin_day < hi)]
        if len(mm) == 0: continue
        B = mm.baseline_loss.sum()
        parts = [f"mix {1 - mm.loss.sum() / B:+.3f}"] if B else []
        for n, r in runs.items():
            rr = r.merge(mm[K], on=K)
            if B: parts.append(f"{n} {1 - rr.loss.sum() / B:+.3f}")
        line += f"\n   {win} n={len(mm)} skill: " + ", ".join(parts)
    print(line)
print("\n== adaptation to the verda regime start on gpurentalprices")
v = pdm[(pdm.src == "gpurentalprices") & (pdm.provider == "verda")].set_index("day")
start = int(v.index[v.k > 0].min()); print("first verda reprice on gpurentalprices:", iso(start))
sids = [s for s, ps in sid_provs.items() if s.startswith("gpurentalprices") and "verda" in ps]
for n, r in runs.items():
    rr = r[r.series_id.isin(sids)].merge(mix[K + ["loss"]], on=K, suffixes=("", "_mix"))
    rr["wk"] = (rr.origin_day - start) // 7
    t = rr.groupby("wk").apply(lambda x: pd.Series({"n": len(x), "skill": 1 - x.loss.sum() / max(x.baseline_loss.sum(), 1e-12),
                                                     "mix": 1 - x.loss_mix.sum() / max(x.baseline_loss.sum(), 1e-12),
                                                     "above_q90_h7": (x[x.horizon_days == 7].y > x[x.horizon_days == 7].q90).mean()}), include_groups=False)
    print(n, "weeks since start:", {int(k): [int(a.n), round(a.skill, 3), round(a.mix, 3), round(a.above_q90_h7, 2)] for k, a in t.iterrows() if k >= -2})
print("(cols: n cells, prov skill, mix skill, share of h=7 truths above q90)")
