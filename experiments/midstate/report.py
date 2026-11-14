"""Dev only. Report variants from runs/midstate/*.parquet: skill, paired diff vs drift and mix, blend with mix,
per-tail coverage by horizon, splits by collector / horizon / outcome bucket, two dev halves, q50 loss ratio."""
import sys
import numpy as np, pandas as pd
from gpuf import compare
pd.set_option("display.width", 250)
KEY = compare.KEY
SPLIT = 20 * 0 + __import__("datetime").date(2026, 9, 11).toordinal()
def load(n): return pd.read_parquet(f"runs/midstate/{n}.parquet")
def pin(y, q, t): return np.maximum(t * (y - q), (t - 1) * (y - q))
def blend(a, b):
    c = a.copy()
    for q in ("q10", "q50", "q90"): c[q] = np.exp(0.5 * np.log(a[q]) + 0.5 * np.log(b[q].values))
    c["loss_q10"], c["loss_q50"], c["loss_q90"] = (pin(c.y, c[q], t) for q, t in (("q10", .1), ("q50", .5), ("q90", .9)))
    c["loss"] = (c.loss_q10 + c.loss_q50 + c.loss_q90) / 3
    return c
def skill(c): return 1 - c.loss.sum() / c.baseline_loss.sum()
def row(n, c, drift, mix):
    pd_ = compare.paired(c, drift); pm = compare.paired(c, mix)
    cov = lambda x: (x.y <= x.q90).mean() - (x.y < x.q10).mean()
    return dict(name=n, skill=skill(c), vs_drift=pd_["d_pooled_skill"], ci_d=tuple(np.round(pd_["ci90_d_pooled_skill"], 3)),
                vs_mix=pm["d_pooled_skill"], ci_m=tuple(np.round(pm["ci90_d_pooled_skill"], 3)), cov=cov(c),
                below_q10=(c.y < c.q10).mean(), above_q90=(c.y > c.q90).mean(),
                q50_ratio=c.loss_q50.sum() / c.baseline_loss.sum() / (1 / 3) if False else c.loss_q50.sum() / (c.baseline_loss.sum() / 1.0) )
if __name__ == "__main__":
    names = sys.argv[1:]
    drift, mix = load("drift"), load("mix")
    cells = {n: load(n) for n in names}
    cells.update({f"blend(mix,{n})": blend(mix, cells[n]) for n in names})
    rows = [row(n, c, drift, mix) for n, c in {"mix": mix, **cells}.items()]
    print(pd.DataFrame(rows).round(4).to_string(index=False))
