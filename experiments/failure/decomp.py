"""Dev only. Where does each method lose? Split every scored cell by what the price actually did,
and bound what perfect knowledge of (a) whether it moves, (b) which way, would be worth."""
import numpy as np, pandas as pd
from gpuf import harness, methods, compare
pd.set_option("display.width", 250)
U = "rental_headline"
MIX = ("mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30})
GBM = ("gbm", {"mode": "full", "train": "all", "save_importance": False})
CH = ("replay", {"path": f"runs/cache/chronos_last_{U}.parquet"})
M = {"drift": ("drift", {}), "mix": MIX, "gbm": GBM, "chronos_last": CH,
     "blend": ("ens", {"members": [list(MIX), list(GBM), list(CH)]})}
R = {k: harness.evaluate(methods.get(m, **p), "dev", U, name=m, params=p).cells for k, (m, p) in M.items()}
base = R["drift"]
T = base["baseline_loss"].sum()
r = np.log(base["y"] / base["baseline"])
kind = pd.Series(np.select([r == 0, r.abs() < 0.01, r.abs() < 0.05, r > 0], ["0 no change", "1 move <1%", "2 move 1-5%", "3 up >5%"], "4 down >5%"), index=base.index)
print("cells by outcome, share of cells and of last-value loss:")
print(pd.DataFrame({"cells": kind.value_counts(normalize=True), "base_loss": base.groupby(kind)["baseline_loss"].sum() / T}).round(3).sort_index().to_string())
print("\nby horizon, share of cells unchanged:", base.groupby("horizon_days").apply(lambda v: (v.y == v.baseline).mean()).round(3).to_dict())
print("\nloss as a fraction of total last-value loss, by outcome (lower is better; last value = base_loss above):")
tab = {k: c.groupby(kind.values)["loss"].sum() / T for k, c in R.items()}
print(pd.DataFrame(tab).round(4).to_string())
print("\nsame by quantile for the blend (q10 / q50 / q90 parts):")
b = R["blend"]; print((b.groupby(kind.values)[["loss_q10", "loss_q50", "loss_q90"]].sum() / T / 3).round(4).to_string())

# oracles, built on the blend's quantiles
def pin(y, q, t): return np.maximum(t * (y - q), (t - 1) * (y - q))
def score(q10, q50, q90, c=b): return (pin(c.y, q10, .1) + pin(c.y, q50, .5) + pin(c.y, q90, .9)).sum() / 3
print("\noracle bounds (pooled skill vs last value):")
print(" blend as is                      ", round(1 - b.loss.sum() / T, 4), "  [check]", round(1 - score(b.q10, b.q50, b.q90) / T, 4))
nc = (b.y == b.baseline).to_numpy()
print(" know WHETHER it moves (collapse interval on no-change cells)", round(1 - score(np.where(nc, b.baseline, b.q10), np.where(nc, b.baseline, b.q50), np.where(nc, b.baseline, b.q90)) / T, 4))
up = (b.y > b.baseline).to_numpy(); dn = (b.y < b.baseline).to_numpy()
q10d = np.where(up, b.baseline, b.q10); q90d = np.where(dn, b.baseline, b.q90)
print(" know DIRECTION only (clip the wrong side to last value)      ", round(1 - score(q10d, b.q50, q90d) / T, 4))
print(" know both                                                    ", round(1 - score(np.where(nc, b.baseline, q10d), np.where(nc, b.baseline, b.q50), np.where(nc, b.baseline, q90d)) / T, 4))
# per-cell best constant symmetric scale of the blend's log width (hindsight, one scale per horizon)
for h, g in b.groupby("horizon_days"):
    best = min(((score(g.baseline * (g.q10 / g.baseline) ** s, g.q50, g.baseline * (g.q90 / g.baseline) ** s, g), s) for s in np.arange(0.2, 3.01, 0.1)))
    print(f" h={h}: blend loss {g.loss.sum()/g.baseline_loss.sum():.4f} of base; best hindsight width scale {best[1]:.1f} -> {best[0]/g.baseline_loss.sum():.4f}")

# concentration
s = b.groupby("series_id").agg(loss=("loss", "sum"), base=("baseline_loss", "sum")); s["d"] = R["drift"].groupby("series_id")["loss"].sum()
s = s.sort_values("base", ascending=False); s["cum_base"] = s.base.cumsum() / T
print("\ntop series by last-value loss (blend skill, drift skill, cumulative share):")
print(pd.DataFrame({"blend": 1 - s.loss / s.base, "drift": 1 - s.d / s.base, "cum": s.cum_base}).head(10).round(3).to_string())
d = b.groupby("origin_date").agg(loss=("loss", "sum"), base=("baseline_loss", "sum")).sort_values("base", ascending=False)
print("\ntop origin days by last-value loss; share of total in top 5 days:", round(d.base.head(5).sum() / T, 3), "| top 10:", round(d.base.head(10).sum() / T, 3), "of", len(d))
b.assign(kind=kind.values, r=r.values).to_parquet("runs/failure/blend_dev_cells.parquet")
