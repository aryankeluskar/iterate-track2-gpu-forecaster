"""Dev only. Compare saved hazard cells with mix and drift: paired differences, offline log-quantile blend with
mix (same rule as `ens`), outcome buckets, and where the probability-to-pinball conversion loses.

Usage: PYTHONPATH=src .venv/bin/python experiments/hazard/compare_cells.py TAG [TAG ...]
"""
import sys

import numpy as np
import pandas as pd

from gpuf import compare

D = "runs/hazard/"
K = compare.KEY
pd.set_option("display.width", 250)


def pin(y, q, t):
    return np.maximum(t * (y - q), (t - 1) * (y - q))


def rescore(c):
    c = c.copy()
    c["loss"] = (pin(c.y, c.q10, .1) + pin(c.y, c.q50, .5) + pin(c.y, c.q90, .9)) / 3
    return c


def blend(a, b, wa=0.5):
    m = a.merge(b[K + ["q10", "q50", "q90"]], on=K, suffixes=("", "_b"))
    for q in ("q10", "q50", "q90"):
        m[q] = np.exp(wa * np.log(m[q]) + (1 - wa) * np.log(m[q + "_b"]))
    return rescore(m[a.columns])


def sk(c):
    return 1 - c.loss.sum() / c.baseline_loss.sum()


def pr(name, a, b):
    p = compare.paired(a, b)
    return f"{name}: d={p['d_pooled_skill']:+.4f} ci90=[{p['ci90_d_pooled_skill'][0]:+.4f},{p['ci90_d_pooled_skill'][1]:+.4f}]"


mix, drift = pd.read_parquet(D + "cells_mix.parquet"), pd.read_parquet(D + "cells_drift.parquet")
chk = rescore(mix)
assert np.allclose(chk.loss, mix.loss), "loss definition mismatch"
T = drift.baseline_loss.sum()
r = np.log(drift.y / drift.baseline)
bucket = pd.Series(np.select([r == 0, r.abs() < 0.01, r.abs() < 0.05, r > 0],
                             ["0 none", "1 <1%", "2 1-5%", "3 up>5%"], "4 dn>5%"), index=drift.index)
key = drift[K].assign(bucket=bucket.values)
print(f"drift {sk(drift):.4f}  mix {sk(mix):.4f}")
for tag in sys.argv[1:]:
    h = pd.read_parquet(D + f"cells_{tag}.parquet").sort_values(K).reset_index(drop=True)
    bl = blend(h, mix)
    cov = ((h.y >= h.q10) & (h.y <= h.q90)).mean()
    print(f"\n== {tag}: skill {sk(h):.4f} cov {cov:.3f} | blend50 with mix {sk(bl):.4f}")
    print("  ", pr("vs drift", h, drift), "|", pr("vs mix", h, mix), "|", pr("blend vs mix", bl, mix))
    for w in (0.25, 0.75):
        print(f"   blend w_hazard={w}: {sk(blend(h, mix, w)):.4f}")
    rows = {}
    for nm, c in (("drift", drift), ("mix", mix), (tag, h), ("blend", bl)):
        c = c.merge(key, on=K)
        rows[nm] = c.groupby("bucket").loss.sum() / T
    print("  loss share of last-value total by outcome bucket:")
    print(pd.DataFrame(rows).round(4).to_string())
    for col in ("source_id", "horizon_days"):
        m = h.merge(mix[K + ["loss"]], on=K, suffixes=("", "_m"))
        print(f"  gain over mix by {col} (share of total base loss):",
              (m.groupby(col).apply(lambda v: (v.loss_m.sum() - v.loss.sum()) / T)).round(4).to_dict())
    try:
        L = pd.read_parquet(D + f"clf_{tag}.parquet")
        m = h.merge(mix[K + ["q10", "q50", "q90", "loss"]], on=K, suffixes=("", "_m")).merge(
            L[K + ["p0", "pu", "pd", "cls"]], on=K)
        m["pbin"] = pd.cut(m.p0, [0, .5, .7, .8, .9, 1.0], include_lowest=True)
        coll = m.assign(q10=m.baseline, q90=m.baseline, q50=m.baseline)
        m["loss_mix_collapsed"] = rescore(coll).loss
        print("  by predicted P(no change): loss / base-loss total, hazard vs mix vs mix with all three quantiles = last")
        print(m.groupby("pbin", observed=True).apply(lambda v: pd.Series({
            "n": len(v), "obs_p0": (v.cls == 0).mean(), "hazard": v.loss.sum() / T, "mix": v.loss_m.sum() / T,
            "mix_collapsed": v.loss_mix_collapsed.sum() / T,
            "w_hz": np.log(v.q90 / v.q10).mean(), "w_mix": np.log(v.q90_m / v.q10_m).mean()})).round(4).to_string())
        print("  quantile parts, hazard minus mix (share of T):",
              {q: round(float(((pin(m.y, m[q], t) - pin(m.y, m[q + '_m'], t)).sum() / 3 / T)), 4)
               for q, t in (("q10", .1), ("q50", .5), ("q90", .9))})
    except FileNotFoundError:
        pass
