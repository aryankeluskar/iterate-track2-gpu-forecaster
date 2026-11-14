"""Dev only. Choose tail levels / side scales on the first half of dev origins, check on the second half.
Usage: tails.py GRID.parquet [levels|scales]"""
import itertools, sys
import numpy as np
from gpuf import harness, methods

g, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "levels")
if mode == "levels":
    cands = [dict(lo=lo, hi=hi) for lo, hi in itertools.product([0.025, 0.05, 0.1, 0.15], [0.85, 0.9, 0.95, 0.975])]
else:
    cands = [dict(sdn=a, sup=b) for a, b in itertools.product([0.5, 0.75, 1.0, 1.5], [0.75, 1.0, 1.5, 2.0, 3.0])]
res = []
for p in cands:
    c = harness.evaluate(methods.get("fm2", grids=[g], **p), "dev", "rental_headline").cells
    mid = np.sort(c.origin_day.unique())[len(c.origin_day.unique()) // 2]
    sk = [1 - x.loss.sum() / x.baseline_loss.sum() for x in (c[c.origin_day < mid], c[c.origin_day >= mid], c)]
    h7 = c[c.horizon_days == 7]
    res.append((p, *sk, (h7.y > h7.q90).mean(), (h7.y < h7.q10).mean()))
base = [r for r in res if r[0] in (dict(lo=0.1, hi=0.9), dict(sdn=1.0, sup=1.0))][0]
best = max(res, key=lambda r: r[1])
for r in sorted(res, key=lambda r: -r[1])[:6] + [base]:
    print(r[0], "first=%+.4f second=%+.4f all=%+.4f h7_above_q90=%.3f h7_below_q10=%.3f" % r[1:])
print("CHOSEN on first half:", best[0], "second half %+.4f vs default %+.4f (diff %+.4f)" % (best[2], base[2], best[2] - base[2]))
