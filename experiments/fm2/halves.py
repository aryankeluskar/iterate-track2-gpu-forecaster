"""Dev only. Pretrained width vs mix by dev half: width, coverage and the loss-dominant series."""
import sys
import numpy as np, pandas as pd
from gpuf import compare, harness, methods
K = compare.KEY
fm = harness.evaluate(methods.get("fm2", grids=[sys.argv[1]]), "dev", "rental_headline").cells
mx = harness.evaluate(methods.get("replay", path="runs/fm2/mix_dev_rental_headline.parquet"), "dev", "rental_headline").cells
c = fm.merge(mx[K + ["q10", "q90", "loss"]], on=K, suffixes=("", "_m"))
mid = np.sort(c.origin_day.unique())[25]
c["half"] = np.where(c.origin_day < mid, 1, 2)
c["wr"] = np.log(c.q90 / c.q10) - np.log(c.q90_m / c.q10_m)
c["above"], c["above_m"] = c.y > c.q90, c.y > c.q90_m
for (hf, h), x in c.groupby(["half", "horizon_days"]):
    B = x.baseline_loss.sum()
    print(hf, h, f"base_loss={B:.1f} skill_fm={1 - x.loss.sum() / B:+.3f} skill_mix={1 - x.loss_m.sum() / B:+.3f} "
          f"mean_logwidth_fm-mix={x.wr.mean():+.4f} above_q90 fm={x.above.mean():.3f} mix={x.above_m.mean():.3f} "
          f"cov fm={((x.y >= x.q10) & (x.y <= x.q90)).mean():.2f} mix={((x.y >= x.q10_m) & (x.y <= x.q90_m)).mean():.2f}")
for hf, x in c.groupby("half"):
    B = c[c.half == hf].baseline_loss.sum()
    s = x.groupby("series_id").apply(lambda g: pd.Series(dict(share=g.baseline_loss.sum() / B, gain=(g.loss_m.sum() - g.loss.sum()) / B)), include_groups=False)
    print("half", hf, "top loss series:\n", s.sort_values("share").tail(4).round(3).to_string())
