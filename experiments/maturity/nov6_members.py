"""Per-member forecasts of the submitted blend for the 37 scored series at origin 2026-11-06 (no truth exists; nothing is scored).
Reads the cutoff history the submission uses and the pretrained member files already in runs/final.
Usage: PYTHONPATH=src .venv/bin/python experiments/maturity/nov6_members.py"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np, pandas as pd
from gpuf import data, harness, methods
from gpuf.submit import history, HORIZONS
from gpuf.data import starter_common
hist_path, hist_cat, store = history()
origin = starter_common.day_of(starter_common.parse_date("2026-11-06"))
sids = data.universe("rental_headline")
meta = harness.static_meta(data.load_catalog(str(hist_cat)))
f = methods.get("final", cap="2026-11-06", tag="2026-11-06", universe="rental_all", record=True)
fc, counts = harness.forecast(f, [origin], sids, HORIZONS, store, meta)
rows = []
for (s, o), outs in f.outs.items():
    d, v = store.history(s, o)
    last = float(v[-1])
    r = dict(series=s.replace(".median", "").replace("neocloud_", "").replace("on_demand", "od"), rows=len(v), last=last,
             chg1=np.log(v[-1] / v[-2]) if len(v) > 1 else 0.0, chg3=np.log(v[-1] / v[-4]) if len(v) > 3 else 0.0,
             chg7=np.log(v[-1] / v[-8]) if len(v) > 7 else 0.0, nchg14=int((v[-14:][1:] != v[-14:][:-1]).sum()))
    for m, o_ in outs.items():
        if o_ is not None and 7 in o_:
            q = o_[7]
            r[f"{m}_lo"], r[f"{m}_hi"] = np.log(q[0] / last), np.log(q[2] / last)
    b = fc[(fc.series_id == s) & (fc.horizon_days == 7)].iloc[0]
    r["final_lo"], r["final_hi"] = np.log(b.q10 / last), np.log(b.q90 / last)
    rows.append(r)
T = pd.DataFrame(rows).sort_values("chg3", key=lambda x: -x.abs())
pd.set_option("display.width", 320, "display.max_columns", 60, "display.max_rows", 80, "display.float_format", "{:+.3f}".format)
print("h = 7: log distance of each member's q10 (lo) and q90 (hi) from the last value; sorted by |3-day change| at the origin")
cols = ["series", "rows", "last", "chg1", "chg3", "chg7", "nchg14"] + [f"{m}_{e}" for m in ["mix", "analog", "prov", "fragility", "gbm", "chronos", "fm2", "final"] for e in ("lo", "hi")]
print(T[cols].to_string(index=False))
T.to_csv("experiments/maturity/results/nov6_members.csv", index=False)
