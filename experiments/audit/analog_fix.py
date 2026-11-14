"""Audit item 1, analog follow-up. leak.py found analog's forecasts at validation origins change when rows after the
origin are deleted (not when their values are changed). Cause: AnalogTable.__init__ drops a whole series when it has
fewer than 2 rows or any non-positive value over the table's full span (cap 2026-11-06), so whether a series that
starts just before the origin is in the standardisation sums (sd) depends on whether it has rows after the origin.

This script (no scoring) 1) names the series whose membership depends on post-origin rows at each validation origin,
2) applies the proposed patch by monkeypatching AnalogTable.__init__ and re-runs the deletion/wild test,
3) measures how far the shipped analog and the patched analog differ at all 18 validation origins (forecasts only)
for analog alone and for the queried blend mix + analog.
Usage: PYTHONPATH=src .venv/bin/python experiments/audit/analog_fix.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.argv = [sys.argv[0], "analog"]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import leak as L  # noqa: E402
from gpuf import harness, methods, splits  # noqa: E402
from gpuf.methods import analog as A  # noqa: E402

ORIG_INIT = A.AnalogTable.__init__


def patched_init(self, df, meta, horizons=A.HORIZONS):
    """Same as AnalogTable.__init__ except: non-positive rows are dropped row by row and a series needs one row,
    so a series' membership never depends on rows dated after any origin."""
    self.horizons = tuple(horizons)
    self.series = {}
    rows = []
    for sid, g in df.groupby("series_id", sort=True):
        g = g.sort_values("day")
        g = g[g["value"] > 0]
        if len(g) == 0:
            continue
        days = g["day"].to_numpy(np.int64)
        vals = g["value"].to_numpy(np.float64)
        npv = np.nan_to_num(g["n_providers"].to_numpy(np.float64), nan=1.0)
        F = A._series_features(days, vals, npv)
        outs = {h: A._outcomes(days, vals, h) for h in self.horizons}
        self.series[sid] = (days, vals, F)
        rows.append((sid, days, F, outs))
    self.sids = [r[0] for r in rows]
    code = {s: i for i, s in enumerate(self.sids)}
    self.meta = {s: meta.get(s, (None, None)) for s in self.sids}
    self.day = np.concatenate([r[1] for r in rows])
    self.F = np.vstack([r[2] for r in rows])
    self.sid_code = np.concatenate([np.full(len(r[1]), code[r[0]]) for r in rows])
    self.out = {h: np.concatenate([r[3][h] for r in rows]) for h in self.horizons}
    o = np.argsort(self.day, kind="stable")
    self.day, self.F, self.sid_code = self.day[o], self.F[o], self.sid_code[o]
    self.out = {h: v[o] for h, v in self.out.items()}
    self.cs = np.vstack([np.zeros(A.NF), np.cumsum(self.F, axis=0)])
    self.cs2 = np.vstack([np.zeros(A.NF), np.cumsum(self.F ** 2, axis=0)])
    self._pools = {}
    self._sd = {}


res = {}
# 1) series whose membership in the shipped table depends on rows after a validation origin
S = L.SERIES.copy()
S["day"] = L.SERIES_DAY
S = S[(S["date"] <= "2026-11-06") & S["series_id"].isin(set(L.CAT.loc[L.CAT["table"] == "daily_statistics", "series_id"]))]
S = S.dropna(subset=["value"])
g = S.groupby("series_id")
full_ok = (g["value"].apply(lambda v: (v > 0).all()) & (g.size() >= 2))
res["series_with_nonpositive_value"] = sorted(g["value"].apply(lambda v: (v <= 0).any()).pipe(lambda x: x[x].index).tolist())
dep = {}
for o in splits.VAL + splits.DEV[-3:]:
    h = S[S["day"] <= o].groupby("series_id")["value"]
    trunc_ok = (h.apply(lambda v: (v > 0).all()) & (h.size() >= 2))
    diff = [s for s in trunc_ok.index if bool(trunc_ok[s]) != bool(full_ok[s])] + \
           [s for s in full_ok.index if s not in trunc_ok.index and False]
    dep[pd.Timestamp.fromordinal(o).date().isoformat()] = diff
res["membership_depends_on_future"] = {k: v for k, v in dep.items() if v}

# 2) patched analog under the leak test (deletion and wild, 3 validation + 2 dev origins)
A.AnalogTable.__init__ = patched_init
origins = [L.D(x) for x in ("2026-09-30", "2026-10-06", "2026-10-13", "2026-10-21", "2026-10-30")]
store0 = L.install(L.SERIES, L.RAW, "real")
base = {o: L.run("analog", [o], store0)[0] for o in origins}
res["patched_leak_test"] = {}
for o in origins:
    for kind in ("del", "wild"):
        s, r = L.perturb(o, kind, seed=o % 10007)
        st = L.install(s, r, kind)
        res["patched_leak_test"][f"{pd.Timestamp.fromordinal(o).date()}|{kind}"] = L.compare(base[o], L.run("analog", [o], st)[0])
print(json.dumps(res["patched_leak_test"], indent=0), flush=True)

# 3) shipped vs patched on all validation origins (forecasts only; nothing is scored)
store0 = L.install(L.SERIES, L.RAW, "real")
fixed = {}
for nm, spec in (("analog", L.SPECS["analog"]),
                 ("mix+analog", ("ens", {"members": [list(L.SPECS["mix"]), list(L.SPECS["analog"])]}))):
    out = {}
    for which, init in (("shipped", ORIG_INIT), ("patched", patched_init)):
        A.AnalogTable.__init__ = init
        A._TABLES.clear()
        fc, _ = harness.forecast(methods.get(spec[0], **spec[1]), list(splits.VAL), L.HEAD, (1, 3, 7), store0, L.META)
        out[which] = fc.set_index(["series_id", "origin_day", "horizon_days"]).sort_index()
    a, b = out["shipped"], out["patched"]
    d = np.abs(np.log(a[["q10", "q50", "q90"]].to_numpy() / b[["q10", "q50", "q90"]].to_numpy()))
    fixed[nm] = {"cells": int(len(a)), "cells_differing": int((d.max(1) > 0).sum()),
                 "mean_abs_log_diff": float(d.mean()), "max_abs_log_diff": float(d.max()),
                 "mean_abs_log_diff_q10": float(d[:, 0].mean()), "mean_abs_log_diff_q90": float(d[:, 2].mean()),
                 "mean_log_width_shipped": float(np.log(a.q90 / a.q10).mean()),
                 "mean_log_width_patched": float(np.log(b.q90 / b.q10).mean())}
res["val_origins_shipped_vs_patched"] = fixed
print(json.dumps(fixed, indent=1))
(L.OUT / "analog_fix.json").write_text(json.dumps(res, indent=1, default=str))
