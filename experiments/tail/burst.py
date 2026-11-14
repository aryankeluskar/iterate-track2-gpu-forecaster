"""Is the h=7 upper-tail gap a stable miscalibration or a few burst days? Dev only, per-origin-day error series."""
import numpy as np, pandas as pd
from gpuf import harness, methods
pd.set_option("display.width", 250)
U = "rental_headline"
MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
ENS3 = ["ens", {"members": [["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}], ["mix", {"pool": "cc", "k": 20, "state": "dirk", "sk": 7, "hl": 30}], ["mix", {"pool": "all", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]]}]
for name, base in (("mix", MIX), ("ens3", ENS3)):
    c = harness.evaluate(methods.get(base[0], **base[1]), "dev", U, name=name).cells
    c = c[c.horizon_days == 7].copy()
    c["ex"] = (c.y > c.q90).astype(float)
    c["ex_lo"] = (c.y < c.q10).astype(float)
    # excess above-q90 pinball loss (price units) = 0.9 weight part when y>q90
    c["q90loss"] = c.loss_q90
    d = c.groupby("origin_day").agg(n=("ex", "size"), ex=("ex", "sum"), exlo=("ex_lo", "sum"), q90loss=("q90loss", "sum"), base=("baseline_loss", "sum"))
    d["rate"] = d.ex / d.n
    N = len(d)
    print(f"\n===== base={name}, h=7: {len(c)} cells, {N} origin days; overall above-q90 rate {c.ex.mean():.3f}, below-q10 {c.ex_lo.mean():.3f}")
    s = d.sort_values("ex", ascending=False)
    for k in (3, 5, 10):
        keep = d.drop(s.index[:k])
        print(f" drop top {k} origin days by exceedance count: they hold {s.ex.head(k).sum() / d.ex.sum():.2f} of exceedances; remaining rate {keep.ex.sum() / keep.n.sum():.3f}")
    print(f" share of days with rate>0.10: {(d.rate > .1).mean():.2f}; days with zero exceedance: {(d.ex == 0).mean():.2f}")
    half = N // 2
    for nm, part in (("first half", d.iloc[:half]), ("second half", d.iloc[half:])):
        print(f" {nm}: above-q90 rate {part.ex.sum() / part.n.sum():.3f}, below-q10 {part.exlo.sum() / part.n.sum():.3f}")
    wk = (d.index - d.index[0]) // 7
    print(" weekly above-q90 rate:", d.groupby(wk).apply(lambda g: g.ex.sum() / g.n.sum()).round(3).tolist())
    r = d.rate.to_numpy()
    print(f" per-day rate: lag-1 autocorr {np.corrcoef(r[1:], r[:-1])[0, 1]:.2f}, lag-7 {np.corrcoef(r[7:], r[:-7])[0, 1]:.2f}, std {r.std():.3f} (binomial-iid std would be {np.sqrt(.1 * .9 / d.n.mean()):.3f}, cells overlap so expect higher)")
    # q90 loss concentration
    t = d.q90loss.sort_values(ascending=False)
    print(f" q90 pinball loss: top 5 origin days hold {t.head(5).sum() / t.sum():.2f}, top 10 hold {t.head(10).sum() / t.sum():.2f} of {N}")
    # by collector and series
    g = c.groupby("source_id").agg(rate=("ex", "mean"), n=("ex", "size"))
    print(g.round(3).T.to_string())
    sr = c.groupby("series_id").agg(rate=("ex", "mean"), n=("ex", "size"), q90loss=("q90loss", "sum")).sort_values("q90loss", ascending=False)
    sr["share"] = sr.q90loss / sr.q90loss.sum()
    print(sr.head(6).round(3).to_string())
    # without top-loss series: rate
    print(f" rate excluding top 3 series by q90 loss: {c[~c.series_id.isin(sr.index[:3])].ex.mean():.3f}")
    d.round(4).to_csv(f"experiments/tail/results/burst_days_{name}.csv")
