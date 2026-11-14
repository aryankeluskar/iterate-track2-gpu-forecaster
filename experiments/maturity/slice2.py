"""Second look (dev only): separate maturity from collector and from the first week of October.
Same store and blends as slice.py."""
import datetime as dt
import numpy as np, pandas as pd
import sys; sys.path.insert(0, 'experiments/maturity')
import blendlib
D = blendlib.load()
MEM = blendlib.MEM
loss_of = lambda members: blendlib.loss(D, members)
SYS = {"drift": ["drift"], "mix": ["mix"], "final7": MEM, "no_pre": [m for m in MEM if m not in ("chronos", "fm2")],
       "analog": ["analog"], "prov": ["prov"], "fragility": ["fragility"], "gbm": ["gbm"], "chronos": ["chronos"], "fm2": ["fm2"]}
blendlib.check(D)
for k, m in SYS.items():
    D["L_" + k] = loss_of(m)
D["date"] = D.origin_day.map(lambda o: dt.date.fromordinal(int(o)).isoformat())
C = list(SYS)
def tab(title, groups):
    print(f"\n## {title}")
    print(f"{'slice':<40}{'cells':>6}{'ser':>5}{'orig':>5}{'moved':>7} " + "".join(f"{c:>10}" for c in C))
    for lab, g in groups:
        if not len(g) or g.baseline_loss.sum() <= 0: continue
        print(f"{lab:<40}{len(g):>6}{g.series_id.nunique():>5}{g.origin_day.nunique():>5}{(g.y != g['last']).mean():>7.2f} " +
              "".join(f"{1 - g['L_' + c].sum() / g.baseline_loss.sum():>+10.4f}" for c in C))
H = D[D.in37]
W = [("2026-09-09", "2026-09-17"), ("2026-09-18", "2026-09-24"), ("2026-09-25", "2026-10-01"), ("2026-10-02", "2026-10-06")]
for src in ["fastgpu_daily", "gpurentalprices", "afhubbard"]:
    x = H[H.src == src]
    tab(f"37 headline, {src}, by origin week (rows range in label)",
        [(f"{a}..{b} rows {x[(x.date >= a) & (x.date <= b)].rows.min()}-{x[(x.date >= a) & (x.date <= b)].rows.max()}", x[(x.date >= a) & (x.date <= b)]) for a, b in W])
# interval width relative to mix, by rows, on the 37: is the pretrained width too wide on mature series?
H = H.copy()
for m in ["mix", "chronos", "fm2", "analog", "prov", "fragility", "gbm", "drift"]:
    H["w_" + m] = np.log(H[f"{m}_q90"] / H[f"{m}_q10"])
print("\n## 37 headline: median log width q90/q10 and coverage by member, by rows bucket and horizon 7")
x = H[H.horizon_days == 7]
for lab, g in [("<30", x[x.rows < 30]), ("30-59", x[(x.rows >= 30) & (x.rows < 60)]), ("60-89", x[(x.rows >= 60) & (x.rows < 90)]), ("90+", x[x.rows >= 90])]:
    print(f"{lab:<8} n {len(g):>5}  realised |log change| mean {np.abs(np.log(g.y / g['last'])).mean():.4f}  share moved {(g.y != g['last']).mean():.2f}  " +
          "  ".join(f"{m} w {g['w_' + m].median():.3f} cov {((g.y >= g[m + '_q10']) & (g.y <= g[m + '_q90'])).mean():.2f}" for m in ["mix", "chronos", "fm2", "analog", "prov", "drift"]))
# every posted rental series from the two young collectors, by rows, all origins: does the pattern hold beyond the 37?
for src in ["fastgpu_daily", "gpurentalprices"]:
    x = D[(D.src == src) & D.moved14]
    tab(f"all series with a change in the last 14 days, {src} by rows", [(l, x[m]) for l, m in [("<30", x.rows < 30), ("30-44", (x.rows >= 30) & (x.rows < 45)), ("45-59", (x.rows >= 45) & (x.rows < 60)), ("60+", x.rows >= 60)]])
    tab(f"all series with a change in the last 14 days, {src}, origins 2026-09-25..2026-10-01 vs 2026-10-02..2026-10-06", [(f"{a}..{b}", x[(x.date >= a) & (x.date <= b)]) for a, b in W[2:]])
