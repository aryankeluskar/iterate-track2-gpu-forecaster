"""Post-hoc slices of runs/maturity/cells.parquet (dev only). Blends are equal-weight means of log quantiles over
the members available in the cell, as gpuf.methods.final.blend."""
import datetime as dt, sys
import numpy as np, pandas as pd
import sys; sys.path.insert(0, 'experiments/maturity')
import blendlib
D = blendlib.load()
MEM = blendlib.MEM
loss_of = lambda members: blendlib.loss(D, members)
SYS = {"drift": ["drift"], "mix": ["mix"], "final7": MEM, "orch5": ["mix", "fm2", "analog", "prov", "fragility"],
       "no_chr": [m for m in MEM if m != "chronos"], "no_chr_fm2": [m for m in MEM if m not in ("chronos", "fm2")],
       "mix_an": ["mix", "analog"], "mix_an_prov": ["mix", "analog", "prov"], "mix_an_prov_fr": ["mix", "analog", "prov", "fragility"],
       "f7+drift": MEM + ["drift"], "mix_an_dr": ["mix", "analog", "drift"], "m_a_p_f_dr": ["mix", "analog", "prov", "fragility", "drift"],
       "analog": ["analog"], "prov": ["prov"], "chronos": ["chronos"], "fm2": ["fm2"], "gbm": ["gbm"], "fragility": ["fragility"]}
for k, m in SYS.items():
    D["L_" + k] = loss_of(m)
print('re-blend check, max abs diff vs harness final loss:', blendlib.check(D))
D["date"] = D.origin_day.map(lambda o: dt.date.fromordinal(int(o)).isoformat())
D["active"] = D.moved14   # the median changed in the last 14 days
def tab(title, groups, cols):
    print(f"\n## {title}")
    print(f"{'slice':<34}{'cells':>6}{'ser':>5}{'orig':>5} " + "".join(f"{c:>11}" for c in cols))
    for lab, g in groups:
        if not len(g) or g.baseline_loss.sum() <= 0: continue
        print(f"{lab:<34}{len(g):>6}{g.series_id.nunique():>5}{g.origin_day.nunique():>5} " +
              "".join(f"{1 - g['L_' + c].sum() / g.baseline_loss.sum():>+11.4f}" for c in cols))
A = ["drift", "mix", "final7", "orch5", "no_chr", "no_chr_fm2", "mix_an", "mix_an_prov_fr", "f7+drift", "m_a_p_f_dr"]
M = ["drift", "mix", "analog", "prov", "fragility", "gbm", "chronos", "fm2"]
H37 = D[D.in37]
grp = H37[H37.src == "gpurentalprices"]
tab("gpurentalprices headline (13 series) by origin week: is it rows or dates?", [(f"{a}..{b} rows {g.rows.min()}-{g.rows.max()}", g) for (a, b), g in
     [((a, b), grp[(grp.date >= a) & (grp.date <= b)]) for a, b in [("2026-08-18", "2026-08-31"), ("2026-09-01", "2026-09-14"), ("2026-09-15", "2026-09-24"), ("2026-09-25", "2026-10-01"), ("2026-10-02", "2026-10-06")]]], M)
fg = H37[H37.src == "fastgpu_daily"]
tab("fastgpu headline (20 series) by origin week", [(f"{a}..{b} rows {g.rows.min()}-{g.rows.max()}", g) for (a, b), g in
     [((a, b), fg[(fg.date >= a) & (fg.date <= b)]) for a, b in [("2026-09-08", "2026-09-14"), ("2026-09-15", "2026-09-24"), ("2026-09-25", "2026-10-01"), ("2026-10-02", "2026-10-06")]]], M)
tab("same weeks, blends: gpurentalprices headline", [(f"{a}..{b}", grp[(grp.date >= a) & (grp.date <= b)]) for a, b in [("2026-08-18", "2026-09-14"), ("2026-09-15", "2026-10-01"), ("2026-10-02", "2026-10-06")]], A)
tab("same weeks, blends: fastgpu headline", [(f"{a}..{b}", fg[(fg.date >= a) & (fg.date <= b)]) for a, b in [("2026-09-08", "2026-09-24"), ("2026-09-25", "2026-10-01"), ("2026-10-02", "2026-10-06")]], A)
act = D[D.active & ~D.in37]
B = [("<30", act.rows < 30), ("30-59", (act.rows >= 30) & (act.rows < 60)), ("60-89", (act.rows >= 60) & (act.rows < 90)), ("90+", act.rows >= 90)]
tab("NOT in the 37, median changed in the last 14 days, by rows: members", [(l, act[m]) for l, m in B], M)
tab("NOT in the 37, median changed in the last 14 days, by rows: blends", [(l, act[m]) for l, m in B], A)
for cls in ["neocloud_rate_card", "neocloud_spot", "marketplace_ask", "hyperscaler_spot", "aggregator_cheapest", "hyperscaler_list"]:
    x = D[D.active & (D.cls == cls)]
    tab(f"active, class {cls}, by rows: blends", [(l, x[m]) for l, m in [("<60", x.rows < 60), ("60+", x.rows >= 60)]], A)
    tab(f"active, class {cls}, by rows: members", [(l, x[m]) for l, m in [("<60", x.rows < 60), ("60+", x.rows >= 60)]], M)
tab("in 37: afhubbard hyperscaler spot (4 series, 90+ rows)", [("all 50 origins", H37[H37.src == "afhubbard"])], A)
tab("in 37: afhubbard members", [("all 50 origins", H37[H37.src == "afhubbard"])], M)
