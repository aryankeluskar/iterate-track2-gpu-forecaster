"""Harness runs of the frozen router variants on rental_all dev; skill by part x half, paired intervals, class table,
share of series worse than LV; Sunday (2026-11-06) gate list."""
import json, sys
import numpy as np, pandas as pd
from gpuf import compare, data, harness, methods
sys.path.insert(0, "experiments/allrental")
from lib import SPLIT_DAY
from gpuf.methods.allrental import gated, n_changes

MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
RP = lambda p: ["replay", {"path": p}]
CFG = {
    "allrental_mctg": {"members": [MIX, RP("runs/cache/chronos_last_rental_all.parquet"), RP("runs/cache/timesfm_last_rental_all.parquet"), RP("runs/allrental/gbm.parquet")], "gate_n": 14, "gate_m": 1},
    "allrental_3mix": {"members": [MIX, ["mix", {"pool": "class", "k": 20, "state": "chgk", "sk": 3, "hl": 30}], ["mix", {"pool": "cc", "k": 5, "state": "chgk", "sk": 3, "hl": 30}]], "gate_n": 14, "gate_m": 1},
    "mix_gate": {"members": [MIX], "gate_n": 14, "gate_m": 1},
}
head = set(data.universe("rental_headline"))
runs = {"drift": harness.evaluate(methods.get("drift"), "dev", "rental_all", name="drift").cells,
        "mix": harness.evaluate(methods.get(*MIX[:1], **MIX[1]), "dev", "rental_all", name="mix").cells}
for k, p in CFG.items():
    runs[k] = harness.evaluate(methods.get("allrental", **p), "dev", "rental_all", name="allrental", params=p).cells
parts = {"all": lambda c: np.ones(len(c), bool), "nonhead": lambda c: ~c.series_id.isin(head).to_numpy(), "head": lambda c: c.series_id.isin(head).to_numpy()}
halves = {"full": lambda c: np.ones(len(c), bool), "early": lambda c: (c.origin_day <= SPLIT_DAY).to_numpy(), "late": lambda c: (c.origin_day > SPLIT_DAY).to_numpy()}
out = []
for name, c in runs.items():
    for pn, pf in parts.items():
        for hn, hf in halves.items():
            m = pf(c) & hf(c); x = c[m]
            r = {"method": name, "part": pn, "half": hn, "n_cells": int(m.sum()),
                 "skill": round(1 - x.loss.sum() / x.baseline_loss.sum(), 4),
                 "coverage": round(((x.y >= x.q10) & (x.y <= x.q90)).mean(), 3)}
            s = x.groupby("series_id")[["loss", "baseline_loss"]].sum()
            r["worse_than_lv"] = f"{int((s.loss > s.baseline_loss + 1e-12).sum())}/{len(s)}"
            r["better_than_lv"] = int((s.loss < s.baseline_loss - 1e-12).sum())
            if name not in ("drift", "mix"):
                for ref in ("drift", "mix"):
                    cr = runs[ref]; cr = cr[pf(cr) & hf(cr)]
                    p = compare.paired(x, cr)
                    r[f"d_vs_{ref}"] = f"{p['d_pooled_skill']:+.4f} [{p['ci90_d_pooled_skill'][0]:+.4f},{p['ci90_d_pooled_skill'][1]:+.4f}]"
            out.append(r)
df = pd.DataFrame(out)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
print(df.to_string(index=False))
df.to_csv("experiments/allrental/results/final_summary.csv", index=False)
# class table (full and late), nonhead only and all
rows = []
for name in runs:
    c = runs[name]; c = c.assign(nh=~c.series_id.isin(head))
    for (cl, hf), x in c.groupby(["instrument_class", c.origin_day > SPLIT_DAY]):
        rows.append({"method": name, "class": cl, "half": "late" if hf else "early", "skill": 1 - x.loss.sum() / x.baseline_loss.sum()})
    for cl, x in c.groupby("instrument_class"):
        rows.append({"method": name, "class": cl, "half": "full", "skill": 1 - x.loss.sum() / x.baseline_loss.sum()})
ct = pd.DataFrame(rows).pivot_table(index=["class", "half"], columns="method", values="skill").round(3)
print(ct.to_string()); ct.to_csv("experiments/allrental/results/class_table.csv")
# Sunday list
o = data.starter_common.day_of(data.starter_common.parse_date("2026-11-06"))
store = data.load_store(data.series_path()); cat = data.load_catalog().set_index("series_id")
rows = []
for sid in data.universe("rental_all"):
    d, v = store.history(sid, o)
    if not len(d):
        rows.append((sid, cat.loc[sid, "tier"], "no_history", None, None, None)); continue
    stale = o - int(d[-1]) > 3
    g = gated(d, v, o, 14, 1)
    rows.append((sid, cat.loc[sid, "tier"], "stale" if stale else ("zero_width" if g else "interval"),
                 int(o - d[-1]), n_changes(d, v, o, 14), int(o - d[0])))
sd = pd.DataFrame(rows, columns=["series_id", "tier", "status", "days_since_last", "changes_14d", "history_days"])
sd.to_csv("experiments/allrental/results/sunday_2026-11-06_gate.csv", index=False)
print(sd.groupby(["tier", "status"]).size())
print(sd[sd.status.isin(["stale", "no_history"])].to_string(index=False))
