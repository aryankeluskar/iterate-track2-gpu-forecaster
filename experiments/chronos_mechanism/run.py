"""Why Chronos-Bolt's own median loses on GPU rental prices (dev cells only), and a per-class dose sweep of its reversion.

Method transferred from Track 5 (weight editing): diagnose the failure first, check whether it is one conditional
mechanism, then sweep its strength with both-halves checks instead of switching it on or off.
Inputs: runs/fm2/grid_bs16_rental_all.parquet (raw Chronos-Bolt-small quantile grids, 16-day context, dev origins),
runs/maturity/cells.parquet (dev cells with truth and member quantiles). Run: .venv/bin/python experiments/chronos_mechanism/run.py
"""
import sys, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from gpuf import data

pin = lambda y, a, b, c: (np.maximum(.1 * (y - a), .9 * (a - y)) + np.maximum(.5 * (y - b), .5 * (b - y)) + np.maximum(.9 * (y - c), .1 * (c - y))) / 3
g = pd.read_parquet("runs/fm2/grid_bs16_rental_all.parquet")
m = pd.read_parquet("runs/maturity/cells.parquet").merge(g[["series_id", "origin_day", "horizon_days", "q0.1", "q0.5", "q0.9"]],
                                                         on=["series_id", "origin_day", "horizon_days"])
out = {"cells": len(m), "origins": int(m.origin_day.nunique())}
sk = lambda L, s: 1 - L.sum() / s.baseline_loss.sum()
m["L_raw"] = pin(m.y, m["q0.1"], m["q0.5"], m["q0.9"])
m["L_fm2"] = pin(m.y, m.fm2_q10, m.fm2_q50, m.fm2_q90)
m["L_drift"] = pin(m.y, m.drift_q10, m.drift_q50, m.drift_q90)
m["L_centre_last"] = pin(m.y, m["q0.1"] - m["q0.5"] + m["last"], m["last"], m["q0.9"] - m["q0.5"] + m["last"])
out["skill"] = {k: round(sk(m[c], m), 4) for k, c in [("raw_chronos", "L_raw"), ("raw_chronos_centre_on_last", "L_centre_last"), ("fm2", "L_fm2"), ("drift", "L_drift")]}
m["dev"] = m["q0.5"] / m["last"] - 1
m["moved"] = (m.y / m["last"] - 1).abs() > 1e-6
out["by_truth_moved"] = {str(k): {"cells": len(s), "raw_median_off_last_pct": round(100 * float((s.dev.abs() > 1e-4).mean()), 1),
                                  "loss_raw_over_fm2": round(float(s.L_raw.sum() / s.L_fm2.sum()), 2)} for k, s in m.groupby("moved")}
mv = m[m.moved & (m.dev.abs() > 1e-4)]
out["direction_correct_pct_on_moved"] = round(100 * float((np.sign(mv.dev) == np.sign(mv.y / mv["last"] - 1)).mean()), 1)

# mechanism: does the median move only after a step in the context, and toward the context mean?
st = data.load_store()
rows = []
for (sid, o), grp in m.groupby(["series_id", "origin_day"]):
    d, v = st.history(sid, o)
    d, v = np.asarray(d), np.asarray(v, float)
    v = v[d <= o]
    if len(v) < 17:
        continue
    ctx = v[-16:]
    nsteps = int((np.abs(np.diff(ctx)) > 1e-9).sum())
    cm = ctx.mean() / v[-1] - 1
    for r in grp.itertuples():
        rows.append((r.cls, r.dev, nsteps, cm, r.y / v[-1] - 1))
D = pd.DataFrame(rows, columns=["cls", "dev", "nsteps", "ctxmean", "realized"])
off = D[D.dev.abs() > 1e-4]
out["median_off_last"] = {"cells": len(off), "with_no_step_in_context": int((off.nsteps == 0).sum())}
s = off[(off.nsteps > 0) & (off.ctxmean.abs() > 1e-6)]
out["reversion_by_class"] = {cls: {"n": len(x), "chronos_reverts_pct": round(100 * float((np.sign(x.dev) == np.sign(x.ctxmean)).mean()), 1),
                                   "truth_reverts_pct": round(100 * float(((np.sign(x.realized) == np.sign(x.ctxmean)) & (x.realized.abs() > 1e-6)).mean()), 1),
                                   "truth_unmoved_pct": round(100 * float((x.realized.abs() <= 1e-6).mean()), 1)} for cls, x in s.groupby("cls")}
out["reversion_all_pct"] = round(100 * float((np.sign(s.dev) == np.sign(s.ctxmean)).mean()), 1)

# dose sweep: centre = last + k * (chronos median - last), fm2 widths; both halves of dev
o = np.sort(m.origin_day.unique())
h1 = m.origin_day <= o[len(o) // 2 - 1]
def skill_k(sub, k):
    ctr = sub["last"] + k * (sub["q0.5"] - sub["last"])
    return float(1 - pin(sub.y, sub.fm2_q10 - sub.fm2_q50 + ctr, ctr, sub.fm2_q90 - sub.fm2_q50 + ctr).sum() / sub.baseline_loss.sum())
ks = [0, 0.25, 0.5, 0.75, 1.0]
out["dose"] = {}
for cls, x in list(m.groupby("cls")) + [("in37", m[m.in37])]:
    row = [skill_k(x, k) for k in ks]
    kb = ks[int(np.argmax(row))]
    a, b = x[h1[x.index]], x[~h1[x.index]]
    out["dose"][cls] = {"skill_by_k": dict(zip(map(str, ks), [round(r, 4) for r in row])), "best_k": kb,
                        "gain_over_k0_half1": round(skill_k(a, kb) - skill_k(a, 0), 4), "gain_over_k0_half2": round(skill_k(b, kb) - skill_k(b, 0), 4)}
json.dump(out, open("experiments/chronos_mechanism/results.json", "w"), indent=1)
print(json.dumps(out, indent=1))
