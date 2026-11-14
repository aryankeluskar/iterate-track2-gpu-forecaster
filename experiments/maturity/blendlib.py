"""Re-blend and score from runs/maturity/cells.parquet exactly as the harness does.

Equal-weight mean of log quantiles over the members available in the cell (gpuf.methods.final.blend: one member is
passed through unchanged, none gives the last value), then the harness cleanup (q10 <= q50 <= q90 by the starter's
`monotone`, non-positive values floored at 1e-6), then pinball loss averaged over the three quantiles.
The adviser's review (experiments/advisor/review_maturity.md) found that the first version of slice.py left the
cleanup out, which changed 798 cells; `check()` asserts the seven-member re-blend equals the stored harness loss."""
import numpy as np
import pandas as pd

MEM = ["mix", "gbm", "chronos", "analog", "prov", "fm2", "fragility"]
T = (0.1, 0.5, 0.9)
Q = ("q10", "q50", "q90")


def load():
    D = pd.read_parquet("runs/maturity/cells.parquet")
    D["src"] = D.series_id.str.split(".").str[0]
    D["moved14"] = D.chg14 > 0            # the median changed in the last 14 days (origin-time)
    return D


def quantiles(D, members):
    out = []
    for q in Q:
        X = np.stack([D[f"{m}_{q}"].to_numpy(float) for m in members])
        n = (~np.isnan(X)).sum(0)
        L = np.log(np.maximum(X, 1e-9))
        mean = np.exp(np.nansum(np.where(np.isnan(X), 0.0, L), 0) / np.maximum(n, 1))
        one = np.nansum(np.where(np.isnan(X), 0.0, X), 0)                 # the single available member, unchanged
        out.append(np.where(n == 0, D["last"].to_numpy(), np.where(n == 1, one, mean)))
    q10, q50, q90 = out
    q10, q90 = np.minimum(q10, q50), np.maximum(q90, q50)
    bad = (q10 <= 0) | (q50 <= 0) | (q90 <= 0)
    q10, q50, q90 = (np.where(bad, np.maximum(x, 1e-6), x) for x in (q10, q50, q90))
    return q10, q50, q90


def loss(D, members):
    y = D["y"].to_numpy()
    tot = np.zeros(len(D))
    for t, f in zip(T, quantiles(D, members)):
        d = y - f
        tot += np.maximum(t * d, (t - 1) * d)
    return tot / 3


def check(D):
    d = np.abs(loss(D, MEM) - D["final_loss"].to_numpy()).max()
    assert d < 1e-12, f"re-blend differs from the harness loss by {d}"
    return d


def skill(g, col):
    return 1 - g[col].sum() / g.baseline_loss.sum()
